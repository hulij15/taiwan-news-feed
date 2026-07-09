#!/usr/bin/env python3
"""
Taiwan News Feed - fetch, translate, filter, deduplicate and render.

Pulls RSS feeds defined in feeds_config.py (Taiwan government sources,
CNA wire, local Chinese/English press, and academic/policy coverage),
machine-translates non-English content to English, keeps only items
relevant to Taiwanese politics / diplomacy / culture / international
relations (KEYWORDS filter), removes duplicates, and renders a color-coded
HTML ticker (index.html) via Jinja2. This is a live ticker, not an archive:
only items published within the last 48 hours (--max-age-days, default 2)
are kept, uniformly across every source - the date cutoff is checked
before translation, not after, so stale items don't cost a translation
call before being discarded.

Run periodically (e.g. via cron, or continuously via server.py) to keep the
feed up to date - each run merges newly fetched items into
data/articles.json instead of overwriting it, then re-applies the 48h
cutoff to the merged set.

Usage:
    python fetch_news.py
    python fetch_news.py --no-translate      # skip translation (fast/offline testing)
    python fetch_news.py --max-age-days 7    # widen the window to the last 7 days
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import time
from calendar import timegm
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoneinfo import ZoneInfo

import feedparser
import requests
import urllib3
from dateutil import parser as dateutil_parser
from jinja2 import Environment, FileSystemLoader

# Silence the InsecureRequestWarning triggered by the narrow verify=False
# fallback in fetch_feed_entries() (see comment there for why it exists).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from feeds_config import CATEGORY_STYLES, FEEDS, KEYWORDS

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTICLES_STORE = DATA_DIR / "articles.json"
TRANSLATION_CACHE_FILE = DATA_DIR / "translation_cache.json"
TEMPLATE_DIR = BASE_DIR / "templates"
DEFAULT_OUTPUT = BASE_DIR / "index.html"

# Articles are stored internally as UTC, but displayed in the user's local
# time (Bratislava) since that's what "when was this published" should mean
# to a human reading the ticker.
LOCAL_TZ = ZoneInfo("Europe/Bratislava")
REFRESH_INTERVAL_SECONDS = 15 * 60

REQUEST_TIMEOUT = 20  # seconds, HTTP request timeout when downloading feeds
TRANSLATE_SLEEP = 0.25  # polite delay between uncached translation calls
MAX_ENTRIES_PER_FEED = 60  # cap per-feed items processed per run (some feeds
# return large archives; newer items are what matter on each incremental run)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
CJK_RE = re.compile(r"[一-鿿]")

# Some outlets put channel-promo boilerplate ("subscribe on YouTube...") in
# the RSS summary field instead of real article text (seen on Liberty Times
# video posts). Strip it so the ticker doesn't show ad copy as a summary.
BOILERPLATE_RE = re.compile(r"(訂閱|小鈴鐺|自由追新聞|subscribe.{0,20}youtube)", re.I)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_news")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_html(raw: str) -> str:
    """Remove HTML tags and unescape entities from a feed summary."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text: str, max_len: int = 320) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rsplit(" ", 1)[0] + "…"


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace - used as a dedup key."""
    text = title.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_id(link: str, title: str) -> str:
    key = f"{link}|{normalize_title(title)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def parse_published(entry) -> datetime:
    """Best-effort extraction of a UTC datetime from a feedparser entry.

    dateutil is tried on the raw string FIRST, ahead of feedparser's own
    published_parsed/updated_parsed struct. feedparser's date parser has
    been observed to silently mis-parse non-RFC822 formats - e.g. Taiwan
    Today emits "2026/07/09" and feedparser decodes that as day=1 instead
    of day=9, with no error raised. dateutil parses the same string
    correctly, so it's the more trustworthy source when both are available.
    """
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                dt = dateutil_parser.parse(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError, TypeError):
                pass
    for field in ("published_parsed", "updated_parsed"):
        struct = entry.get(field)
        if struct:
            try:
                return datetime.fromtimestamp(timegm(struct), tz=timezone.utc)
            except (ValueError, OverflowError):
                pass
    return datetime.now(timezone.utc)


def strip_tracking_params(link: str) -> str:
    """Drop the feedburner/utm tracking query string used for dedup matching."""
    return re.sub(r"[?&](utm_[^=&]+|.*feedburner.*)=[^&]*", "", link, flags=re.I).rstrip("?&")


# ---------------------------------------------------------------------------
# Translation (deep-translator, Google backend, free) with disk cache
#
# Maps our feeds_config.py "lang" codes to the source language code Google
# Translate expects. "zh" is pinned to "zh-TW" (Traditional Chinese) rather
# than "auto" or plain "zh" - deep-translator's scraping backend has been
# observed to silently return Traditional Chinese text unchanged instead of
# translating it or raising an error when the source isn't pinned exactly.
# ---------------------------------------------------------------------------
GOOGLE_SOURCE_LANG = {
    "zh": "zh-TW",
    "cs": "cs",
}


class Translator:
    def __init__(self, cache_path: Path, enabled: bool = True):
        self.enabled = enabled
        self.cache_path = cache_path
        self.cache: dict[str, str] = {}
        self._dirty = False
        self._engines: dict[str, object] = {}  # lang -> GoogleTranslator instance
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                log.warning("Could not read translation cache, starting fresh")

    def _get_engine(self, lang: str, target: str):
        key = f"{lang}->{target}"
        if key not in self._engines:
            from deep_translator import GoogleTranslator

            source = GOOGLE_SOURCE_LANG.get(lang, lang)
            self._engines[key] = GoogleTranslator(source=source, target=target)
        return self._engines[key]

    def translate(self, text: str, lang: str = "zh", target: str = "en") -> str:
        text = (text or "").strip()
        if not text:
            return ""
        if not self.enabled:
            return text

        cache_key = hashlib.sha1(f"{lang}->{target}:{text}".encode("utf-8")).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            engine = self._get_engine(lang, target)
            translated = engine.translate(text[:4900])  # deep-translator length limit
            time.sleep(TRANSLATE_SLEEP)
            if translated and translated.strip() == text and lang == "zh" and CJK_RE.search(text):
                log.warning("Translation returned unchanged CJK text: %r", text[:60])
        except Exception as exc:  # noqa: BLE001 - translation backend can fail many ways
            log.warning("Translation failed, keeping original text: %s", exc)
            translated = text

        translated = translated or text
        self.cache[cache_key] = translated
        self._dirty = True
        return translated

    def save(self) -> None:
        if self._dirty:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )


# ---------------------------------------------------------------------------
# Fetch + process
# ---------------------------------------------------------------------------
def fetch_feed_entries(source: dict) -> list:
    log.info("Fetching %s ...", source["name"])
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.SSLError:
        # Some *.gov.tw sites ship a certificate chain (Taiwan GRCA) that is
        # missing the Subject Key Identifier extension modern OpenSSL wants,
        # so strict verification fails even though the domain itself is
        # legitimate. Retry once without verification as a documented,
        # narrow fallback (read-only public RSS, no credentials involved).
        log.warning(
            "%s: TLS chain verification failed (known issue with some "
            "*.gov.tw certificates) - retrying without verification",
            source["name"],
        )
        try:
            response = requests.get(
                source["url"],
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                verify=False,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            log.error("Failed to fetch %s: %s", source["name"], exc)
            return []
    except requests.RequestException as exc:
        log.error("Failed to fetch %s: %s", source["name"], exc)
        return []

    parsed = feedparser.parse(response.content)

    if parsed.bozo and not parsed.entries:
        log.warning("Feed %s could not be parsed: %s", source["name"], parsed.get("bozo_exception"))
        return []

    entries = parsed.entries[:MAX_ENTRIES_PER_FEED]
    log.info("  -> %d entries (processing %d)", len(parsed.entries), len(entries))
    return entries


KEYWORD_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b", re.I) for k in KEYWORDS]


def is_relevant(title_en: str, summary_en: str) -> bool:
    # Word-boundary matching, not plain substring - otherwise short keywords
    # like "pla" or "who" false-positive inside unrelated words such as
    # "platforms", "Plastics", or the sentence "...those who meet...".
    haystack = f"{title_en} {summary_en}"
    return any(pattern.search(haystack) for pattern in KEYWORD_PATTERNS)


def process_source(source: dict, translator: Translator, cutoff: datetime) -> list[dict]:
    articles = []
    skipped_stale = 0
    for entry in fetch_feed_entries(source):
        # Check the date FIRST, before any translation - this is a ticker
        # of what's currently happening, not an archive, so there is no
        # point spending a translation call on an item that prune() would
        # just discard afterwards for being outside the retention window.
        published = parse_published(entry)
        if published < cutoff:
            skipped_stale += 1
            continue

        title_raw = strip_html(entry.get("title", "")).strip()
        summary_raw = strip_html(entry.get("summary", "") or entry.get("description", ""))
        link = (entry.get("link") or "").strip()
        if not title_raw or not link:
            continue
        if BOILERPLATE_RE.search(summary_raw):
            summary_raw = ""

        needs_translation = source["lang"] != "en"
        lang = source["lang"]
        title_en = translator.translate(title_raw, lang=lang) if needs_translation else title_raw

        # Some nominally-English feeds (e.g. a representative office's "News"
        # WordPress category) occasionally carry a Chinese-language post
        # anyway. Opportunistically translate anything that still has CJK
        # characters after the above, regardless of the feed's declared lang.
        if not needs_translation and CJK_RE.search(title_en):
            title_en = translator.translate(title_raw, lang="zh")

        # Check relevance on the (cheap) translated title first, only
        # translating the summary for items that are actually going to be
        # kept - this keeps large archive feeds affordable to translate.
        if not source.get("always_relevant") and not is_relevant(title_en, ""):
            continue

        if summary_raw:
            summary_en = translator.translate(summary_raw, lang=lang) if needs_translation else summary_raw
            if not needs_translation and CJK_RE.search(summary_en):
                summary_en = translator.translate(summary_raw, lang="zh")
        else:
            summary_en = ""

        if not source.get("always_relevant") and not is_relevant(title_en, summary_en):
            continue

        clean_link = strip_tracking_params(link)

        articles.append({
            "id": make_id(clean_link, title_en),
            "title": title_en.strip(),
            "title_original": title_raw if needs_translation else None,
            "summary": truncate(summary_en.strip()),
            "link": link,
            "link_key": clean_link,
            "source": source["name"],
            "category": source["category"],
            "published": published.isoformat(),
        })

    if skipped_stale:
        log.info("  -> skipped %d items older than the retention window", skipped_stale)
    return articles


def get_status() -> dict:
    """Cheap status snapshot for server.py's /api/status polling endpoint -
    reads what's already on disk, doesn't trigger a fetch."""
    articles = load_store()
    generated_at = None
    if DEFAULT_OUTPUT.exists():
        generated_at = datetime.fromtimestamp(
            DEFAULT_OUTPUT.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {"count": len(articles), "generated_at": generated_at}


def load_store() -> list[dict]:
    if ARTICLES_STORE.exists():
        try:
            return json.loads(ARTICLES_STORE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read %s, starting with an empty store", ARTICLES_STORE)
    return []


def save_store(articles: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_STORE.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_and_dedupe(existing: list[dict], new_batches: list[list[dict]]) -> list[dict]:
    by_id: dict[str, dict] = {a["id"]: a for a in existing}
    seen_links = {a.get("link_key", a["link"]) for a in existing}
    seen_titles = {normalize_title(a["title"]) for a in existing}

    added = 0
    for batch in new_batches:
        for art in batch:
            if art["id"] in by_id:
                continue
            if art["link_key"] in seen_links:
                continue
            norm_title = normalize_title(art["title"])
            if norm_title in seen_titles:
                continue
            by_id[art["id"]] = art
            seen_links.add(art["link_key"])
            seen_titles.add(norm_title)
            added += 1

    log.info("Added %d new unique articles", added)
    return list(by_id.values())


def prune(articles: list[dict], max_age_days: int, max_items: int) -> list[dict]:
    # No per-category exceptions: this is a live "what's happening right
    # now" ticker, not an archive - a strict, uniform cutoff applies to
    # every category, including slow-moving ones like Culture. If a source
    # hasn't published anything within the window, it simply doesn't show
    # up until it does - that's the point.
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    kept = [
        a for a in articles
        if datetime.fromisoformat(a["published"]) >= cutoff
    ]
    kept.sort(key=lambda a: a["published"], reverse=True)
    return kept[:max_items]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render_html(articles: list[dict], output_path: Path) -> dict:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("index.html.j2")

    for art in articles:
        dt_utc = datetime.fromisoformat(art["published"])
        dt_local = dt_utc.astimezone(LOCAL_TZ)
        art["published_time"] = dt_local.strftime("%H:%M")
        art["published_date"] = dt_local.strftime("%Y-%m-%d")
        art["published_display"] = dt_local.strftime("%d %b %Y, %H:%M")

    categories_present = sorted(
        {a["category"] for a in articles},
        key=lambda c: list(CATEGORY_STYLES).index(c) if c in CATEGORY_STYLES else 99,
    )

    generated_at_utc = datetime.now(timezone.utc)
    generated_at_local = generated_at_utc.astimezone(LOCAL_TZ)

    html_out = template.render(
        articles=articles,
        category_styles=CATEGORY_STYLES,
        categories_present=categories_present,
        generated_at=generated_at_local.strftime("%d %b %Y, %H:%M"),
        generated_at_iso=generated_at_utc.isoformat(),
        refresh_interval_seconds=REFRESH_INTERVAL_SECONDS,
        total_count=len(articles),
        source_count=len(FEEDS),
    )
    output_path.write_text(html_out, encoding="utf-8")
    log.info("Wrote %s (%d articles)", output_path, len(articles))

    return {"count": len(articles), "generated_at": generated_at_utc.isoformat()}


# ---------------------------------------------------------------------------
# Pipeline entry point - called by both the CLI (main, below) and server.py
# (on-demand "Refresh Now" and the 15-minute background scheduler).
# ---------------------------------------------------------------------------
def run_pipeline(
    no_translate: bool = False,
    max_age_days: int = 2,
    max_items: int = 400,
    output: Path = DEFAULT_OUTPUT,
) -> dict:
    translator = Translator(TRANSLATION_CACHE_FILE, enabled=not no_translate)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    new_batches = []
    for source in FEEDS:
        new_batches.append(process_source(source, translator, cutoff))
        translator.save()  # incremental - a cold run touches a lot of translation
        # calls; saving after every source means an interrupted run doesn't
        # lose all of that work, and a re-run resumes from a warm cache.

    existing = load_store()
    merged = merge_and_dedupe(existing, new_batches)
    final = prune(merged, max_age_days, max_items)
    save_store(final)

    return render_html(final, output)


def main():
    parser = argparse.ArgumentParser(description="Fetch and render the Taiwan news ticker")
    parser.add_argument("--no-translate", action="store_true", help="skip machine translation")
    parser.add_argument("--max-age-days", type=int, default=2, help="drop items older than N days (default: 2 = 48h)")
    parser.add_argument("--max-items", type=int, default=400, help="cap total items kept/rendered")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output HTML path")
    args = parser.parse_args()

    run_pipeline(
        no_translate=args.no_translate,
        max_age_days=args.max_age_days,
        max_items=args.max_items,
        output=args.output,
    )


if __name__ == "__main__":
    main()
