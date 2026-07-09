# Taiwan News Ticker

An automated news ticker (in the spirit of GlobalSecurity.org's country
trackers) focused on Taiwanese politics, diplomacy, culture, cross-strait
relations, and international relations. It pulls RSS feeds from Taiwanese
government sources, the national wire service (CNA, in Chinese, machine-
translated), local press, and international/academic coverage, keeps only
items relevant to the topic, removes duplicates, and renders a color-coded
HTML page (`index.html`) with every non-English headline and summary
translated into English. Run via `server.py` (see Usage below), it also
auto-refreshes itself every 15 minutes and offers a manual "Refresh Now"
button - no separate cron job required.

This is a live "what's happening right now" ticker, not an archive: only
items published in the **last 48 hours** are kept (`--max-age-days`,
default `2`) - anything older is dropped on every run, uniformly across
every source and category, no exceptions. If a slow-moving source hasn't
published anything in the last 48 hours, it simply doesn't appear until it
does.

Every source in `feeds_config.py` was individually checked for two things,
not just "does it return 200 OK":

1. **Does it actually return parseable RSS**, not an HTML shell (a lot of
   modern news sites are client-rendered JS apps whose `/rss` path returns
   a web page, not a feed) or a Cloudflare challenge page.
2. **Does it carry real, current publish dates on its items.** This is the
   one that bit the first version of this project: MOFA's Chinese
   "OpenData" feeds return items with *no date field at all*, so anything
   fetched from them landed at the top of the ticker stamped "now" — a
   press release from 2017 could show up looking like breaking news. See
   "Sources that were dropped" below for what got cut because of this and
   what replaced it.

## Sources

| Source | Category | Language | Notes |
|---|---|---|---|
| MOFA Taiwan — News & Events, Press Releases, Statements & Responses, Background Information, Important Remarks | Official / Government | English | 5 feeds, all with real `pubDate`s |
| Office of the President — News | Official / Government | English | Real `pubDate`, updates same-day |
| CNA — Politics, International, Cross-Strait, Culture | CNA Wire (Chinese) | Chinese → translated | Taiwan's national wire service; only the politics/diplomacy/culture sections, not the full wire |
| Focus Taiwan (CNA English News) | CNA Wire (English) | English | CNA's own English newsroom — separately written, not a machine translation of the Chinese wire |
| Liberty Times — Politics, International, Arts & Culture, Military & Defense | Taiwan Press (Chinese) | Chinese → translated | Section feeds, not the unfiltered "all news" firehose |
| Storm Media (風傳媒) — Politics, International, Cross-Strait | Taiwan Press (Chinese) | Chinese → translated | Very high update frequency, often multiple items per hour - a strong fit for a 48h window |
| ETtoday — Politics, International, Cross-Strait, Military & Defense | Taiwan Press (Chinese) | Chinese → translated | Also very high frequency |
| The News Lens (關鍵評論網) | Taiwan Press (Chinese) | Chinese → translated | General feed (no section split found), so it relies on `KEYWORDS` filtering like the other non-`always_relevant` sources |
| Taipei Times | Taiwan Press (English) | English | |
| Taiwan Today | Taiwan Press (English) | English | Government-run English magazine/wire, diplomacy-heavy |
| Taiwan Today — Culture | Culture | English | Taiwan Review-style long-form culture/heritage features; publishes in batches every few months, so it will often show 0 items within the 48h window - that's expected, not a bug |
| Taiwan Insight (Taiwan Research Hub, U. Nottingham) | Policy / Academic Analysis | English | Academic magazine covering Taiwan politics, culture and identity |
| Global Taiwan Brief (Global Taiwan Institute) | Policy / Academic Analysis | English | Biweekly DC-based Taiwan/US policy think tank - often 0 items within 48h |
| The Diplomat — Taiwan tag | Policy / Academic Analysis | English | Asia-Pacific security/politics magazine, pre-scoped to the Taiwan tag - also often 0 items within 48h |

29 feeds total. CNA, Liberty Times, Storm Media, ETtoday and The News Lens
are Chinese-language and go through translation — per project requirement,
CNA content is kept in its original Chinese source and translated, rather
than substituted wholesale by Focus Taiwan's English desk (which is
included as an *additional*, separately-bylined source, not a
replacement).

## How it works

1. **`feeds_config.py`** — declares every RSS source, its category (for the
   color badges), its language, and the `KEYWORDS` relevance filter.
2. **`fetch_news.py`** — for each run, for every feed in `FEEDS`:
   - downloads it (with a Traditional-Chinese-aware translator and a narrow
     TLS fallback for some `*.gov.tw` certificates — see comments in the
     code),
   - extracts each item's publish date, preferring `dateutil`'s parse of the
     raw date string over feedparser's own `*_parsed` struct (feedparser's
     parser has been observed to silently mis-parse non-RFC822 dates — see
     "Known limitations"),
   - **checks that date against the 48-hour cutoff immediately, before any
     translation happens.** This matters: translating an item just to have
     `prune()` discard it minutes later for being stale is pure waste -
     MOFA's "Important Remarks" feed alone can return 60 fetched entries
     that are *all* older than 48 hours, skipping translation for all of
     them saves real time on every run,
   - strips known ad/subscribe boilerplate that some outlets put in the
     summary field instead of real article text,
   - translates the title/summary to English via `deep-translator` (Google
     backend, free) for anything not already English,
   - caches every translation call in `data/translation_cache.json`, saved
     incrementally after each source (not just once at the end) so an
     interrupted run doesn't lose the translation work it already did,
   - drops anything that doesn't match `KEYWORDS` (sources whose entire
     scope is already on-topic — MOFA, the President's Office, The Diplomat's
     Taiwan tag, Taiwan Insight, Global Taiwan Brief — are exempt via
     `always_relevant: True`),
   - deduplicates against everything already stored (by link and by
     normalized title),
   - merges the new items into `data/articles.json` (a rolling history —
     each run *adds* to the store, it doesn't replace it) and prunes items
     older than `--max-age-days` (default 2 = 48h) / beyond `--max-items`,
   - renders `templates/index.html.j2` with Jinja2 into `index.html`.

Because state lives in `data/articles.json` and every item now has a
trustworthy publish date, running the script on a schedule (cron, GitHub
Actions, etc.) builds up a real, correctly-ordered stream instead of just
showing whatever happens to be in the RSS feeds' latest 20-60 items at any
given moment - while `prune()` keeps it capped to the last 48 hours on
every run, so the store never becomes an archive.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Option A — live dashboard (recommended)

```bash
python server.py            # http://localhost:8850
PORT=9000 python server.py  # use a different port
```

This starts a small local Flask server that:

- runs the fetch/translate/render pipeline immediately, then automatically
  **every 15 minutes** in the background (`fetch_news.REFRESH_INTERVAL_SECONDS`),
  so new articles get pulled in on their own without you doing anything;
- serves the page at `http://localhost:8850`, where a **🔄 Refresh Now**
  button triggers an on-demand refresh (disabled with a status message
  while one is already in progress, so clicking it doesn't collide with the
  background schedule);
- the open page itself polls a small status endpoint once a minute and
  reloads automatically the moment new content has actually landed - not on
  a blind timer, so it won't jump/reload if nothing changed.

Leave `python server.py` running (e.g. in a terminal tab, `tmux`, or as a
login item) and just keep the browser tab open or revisit it whenever.

### Option B — one-off static generation

```bash
python fetch_news.py                    # fetch, translate, render index.html (last 48h)
python fetch_news.py --no-translate     # skip translation (fast, for testing/offline)
python fetch_news.py --max-age-days 7   # widen the window to the last 7 days instead of 48h
python fetch_news.py --max-items 200    # cap the stored/rendered article count
python fetch_news.py --output out.html  # write somewhere other than index.html
```

A cold run (empty translation cache) takes a few minutes because of the
Chinese→English translation calls; once `data/translation_cache.json` is
warm, a run typically finishes in under a minute. The date-based early skip
(see "How it works") means the cold-run cost mostly scales with how much
*actually happened in the last 48 hours*, not with how large or old a
feed's archive is.

Useful if you'd rather drive updates from cron/GitHub Actions instead of
keeping a server process running, e.g. every 15 minutes:

```cron
*/15 * * * * cd /path/to/taiwan-news-feed && venv/bin/python fetch_news.py >> fetch.log 2>&1
```

With this option, opening `index.html` directly (`file://...`) works fine
for reading, but the "Refresh Now" button and live auto-reload won't do
anything (there's no server to talk to) - it'll show a message telling you
to run `python server.py` instead. `index.html` itself is still regenerated
by the cron job either way.

## Adding a new RSS source

Before adding a source, verify it the same way this project's sources were
verified — don't just check for HTTP 200:

```bash
curl -sIL -A "Mozilla/5.0" "https://example.com/rss.xml"        # is it actually XML?
curl -s -A "Mozilla/5.0" "https://example.com/rss.xml" | grep pubDate   # does it have real per-item dates?
```

Then open `feeds_config.py` and append an entry to the `FEEDS` list:

```python
{
    "name": "Some Outlet - Section",   # shown as the source badge
    "url": "https://example.com/rss.xml",
    "category": "press_en",            # one of CATEGORY_STYLES (see below)
    "lang": "en",                      # "en" = no translation, otherwise a source language code
},
```

Field reference:

| Field              | Meaning                                                                                          |
|--------------------|----------------------------------------------------------------------------------------------------|
| `name`             | Display name for the source badge/label.                                                          |
| `url`              | RSS/Atom feed URL.                                                                                 |
| `category`         | Key into `CATEGORY_STYLES` — controls the color badge. Add a new category there if needed.        |
| `lang`             | `"en"` skips translation. Anything else is treated as a source language and translated - `"zh"` (Traditional Chinese) is already mapped in `GOOGLE_SOURCE_LANG` (`fetch_news.py`); add new ones there as needed. |
| `always_relevant`  | Optional, default `False`. Set `True` to bypass the `KEYWORDS` filter (use for sources whose entire scope is already on-topic, e.g. a ministry's own press releases, or a magazine that only covers Taiwan politics/culture). |

To add a new color-coded category, add an entry to `CATEGORY_STYLES` at the
top of `feeds_config.py`:

```python
CATEGORY_STYLES["think_tank"] = {
    "label": "Think Tank / Analysis",
    "icon": "📚",
    "color": "#16a085",
    "text_color": "#ffffff",
}
```

To broaden or narrow what counts as "relevant", edit the `KEYWORDS` list —
it's matched with word-boundaries, case-insensitively, against the
**English** (post-translation) title and summary.

### Notes on translation

`Translator` in `fetch_news.py` keeps one `GoogleTranslator` engine per
source language, keyed off the feed's `lang` field via `GOOGLE_SOURCE_LANG`
(currently `"zh"` → `"zh-TW"`). Chinese is pinned to `"zh-TW"` (Traditional
Chinese) rather than `"auto"` deliberately: deep-translator's free scraping
backend is unreliable with `source="auto"` on Traditional Chinese text — it
silently returns the original, untranslated text instead of raising an
error (confirmed while testing CNA/Liberty Times headlines).

To add a source in a new language, add its Google Translate language code
to `GOOGLE_SOURCE_LANG` in `fetch_news.py` if the feed's `lang` value
wouldn't already match Google's code directly, then use that `lang` value
in the feed's `feeds_config.py` entry - no other code changes needed.

An earlier version of this project translated everything to Slovak for
final display as a two-stage pipeline (source language → English for
relevance checking → Slovak for display). It was reverted - the free
Google Translate output for Slovak wasn't good enough - but `Translator`
still accepts an arbitrary `target` language per call if you want to
revisit that (or try a different target language) later.

One more wrinkle this surfaced: a feed can be *nominally* English (e.g. a
representative office's WordPress "News" category) while occasionally
containing a post actually written in Chinese. `process_source()` checks
whether the "English" title/summary still contains CJK characters after
being taken as-is, and opportunistically routes just that item through the
Chinese translator if so - so a feed's declared `lang` doesn't have to be
100% accurate for every single item it ever publishes.

### Sources that were dropped or replaced, and why

- **MOFA's Chinese "OpenData" feeds** (`www.mofa.gov.tw/OpenData.aspx?...`)
  — dropped. No date field on any item (see intro above), and one of them
  ("Statements & Press Releases") returned 1,000 mixed-vintage items with
  no way to tell old from new. Replaced with MOFA's **English** feeds
  (`en.mofa.gov.tw/OpenData.aspx?...`), which carry a real `<pubDate>` per
  item and are already in English.
- **Office of the President's Chinese feeds** — same issue pattern avoided
  by using the English `english.president.gov.tw/RSSNEWS.aspx` feed instead
  (real `pubDate`s, confirmed same-day updates). Its Gazette feed (formal
  legal announcements/appointments) was left out as out-of-scope for a news
  ticker.
- **CNA's non-political sections** (finance, technology, life & health,
  society, local, sports, entertainment) — dropped. They were pulled in an
  earlier version of this project because their URLs were on hand, but
  they're not politics/diplomacy/culture/international-relations content,
  and translating ~200 extra headlines a run for no thematic benefit was
  pure overhead. Kept: Politics, International, Cross-Strait, Culture.
- **Liberty Times' `rss/all.xml` firehose** — replaced with its dedicated
  section feeds (`politics.xml`, `world.xml`, `art.xml`, `def.xml`), which
  exist and are just as fresh, but don't require filtering out sports/
  entertainment/lifestyle noise first.
- **Taiwan News** (taiwannews.com.tw) — no working public RSS endpoint
  found; the site is a client-rendered Next.js app and `/rss` returns an
  HTML page, not a feed.
- **Youth Daily News** (ydn.com.tw) — its `/rss/` path is blocked by
  Cloudflare (403) even for plain feed requests.
- **Mainland Affairs Council** (mac.gov.tw) — has a documented English RSS
  URL, but the entire site returned HTTP 403 to every request made while
  building this project (looks like a network/WAF block, possibly
  geo-based). Worth retrying later — it would be a strong cross-strait
  source if reachable; see the commented-out shape in `feeds_config.py`'s
  history if you want to try again.
- **Xinhua / news.cn Taiwan channel** — no public RSS feed could be located
  for this section.
- **The Japan Times** — dropped outright (its Taiwan-tag feed is behind a
  Cloudflare JS challenge, and its general feed was the weakest thematic
  fit once the "International Press" category was removed in favor of
  "Culture"). **The Diplomat — Taiwan tag** was kept but recategorized from
  "International Press" into "Policy / Academic Analysis," where it fits
  better anyway.
- **World News API** (`api.worldnewsapi.com`) — requires a paid/registered
  API key, which wasn't available for this project, so it was left out
  entirely rather than half-wired. It could be added as its own function
  in `fetch_news.py` (call the API, map its JSON response into the same
  article dict shape used elsewhere) gated behind an optional
  `WORLDNEWS_API_KEY` environment variable.

## Design notes

- **At-a-glance topic**: every article card has a color-coded left border
  and an icon+label badge (🏛️ government, 📡 wire, 📰 press, 🎭 culture,
  📚 analysis) so you can tell what kind of source it's from without
  reading the byline.
- **Local time next to every headline**: each item shows the original
  publish date/time converted to `Europe/Bratislava`, formatted as
  `09 Jul 2026, 14:54`, right above its title. Internally everything is
  stored as UTC (`data/articles.json`); the Bratislava conversion happens
  only at render time in `render_html()` (`fetch_news.py`), so changing the
  displayed timezone later is a one-line edit (`LOCAL_TZ` at the top of the
  file).
- **Freshness indicator**: the header shows a pulsing green dot, the total
  article/source counts, and "updated ... — N minutes ago", which ticks
  live via JavaScript without needing a page reload.

## Project structure

```
taiwan-news-feed/
├── fetch_news.py              # fetch/translate/filter/render pipeline
├── server.py                  # live dashboard: 15-min auto-refresh + Refresh Now + status API
├── feeds_config.py            # sources, categories, icons, keywords
├── requirements.txt
├── templates/
│   └── index.html.j2          # Jinja2 template for the ticker page
├── data/
│   ├── articles.json          # persisted/deduplicated article store
│   └── translation_cache.json # translation cache (avoids re-translating)
├── index.html                 # generated output
└── README.md
```

## Known limitations

- Translation quality depends on Google's free translate endpoint via
  `deep-translator`; it's not perfect, especially for names and idioms.
  Occasionally the same term is translated inconsistently between a title
  and its summary (e.g. one CNA item translated "台北市" as "Taipei City"
  in the summary but "Beijing City" in the title) — this is an upstream MT
  quirk, not a filtering bug.
- Relevance filtering is a simple keyword match (word-boundary, not
  substring), not semantic — it can miss stories that don't use any listed
  keyword, or occasionally keep an off-topic story that happens to mention
  one (e.g. "United States" appearing in an unrelated business story).
  Tune `KEYWORDS` in `feeds_config.py` to taste. Deliberately excluded:
  bare terms like "taiwan"/"taipei" (see the comment above `KEYWORDS` — on
  a Taiwan-based outlet, nearly every headline mentions Taiwan, so those
  terms alone would let everything through, including tax/health/sports
  stories).
- `feedparser`'s built-in date parser has been observed to silently
  mis-parse non-RFC822 date formats (Taiwan Today emits `2026/07/09`, which
  feedparser decoded as day=1 instead of day=9, with no error raised).
  `parse_published()` now tries `dateutil` on the raw date string first and
  only falls back to feedparser's parsed struct if that fails — but if you
  add a source with an unusual date format, it's worth spot-checking
  `data/articles.json` after the first run.
- Some `*.gov.tw` sites present a TLS certificate chain that fails strict
  verification (missing Subject Key Identifier extension). `fetch_news.py`
  retries those specific requests without verification as a documented,
  narrow fallback — see the comment in `fetch_feed_entries()`.
- Mainland Affairs Council (mac.gov.tw) could not be reached at all while
  building this (HTTP 403 site-wide) — see "Sources that were dropped".
- Browsers aggressively cache static files by default. `server.py`'s `/`
  and `/api/status` routes explicitly send `Cache-Control: no-store` -
  without it, a reload after clicking "Refresh Now" could serve a stale
  cached copy of `index.html` via a `304 Not Modified` even though the file
  had genuinely changed on disk (observed while testing the button).
- Local-time display uses Python's `zoneinfo` with the `tzdata` package
  (needed because not every OS ships an IANA timezone database
  system-wide - macOS/Linux usually do, but it's not guaranteed everywhere
  `pip install`s might run). If you change `LOCAL_TZ` in `fetch_news.py` to
  a different zone, no other code changes are needed.
- The 15-minute background refresh and the "Refresh Now" button share one
  lock (`server.py`'s `_refresh_lock`); if they'd overlap, the button just
  returns "a refresh is already running" rather than queuing - click it
  again a few seconds later.
- The 48-hour cutoff is uniform, with no per-category exception. Sources
  that don't publish often (Taiwan Today Culture, Global Taiwan Brief, The
  Diplomat's Taiwan tag) will frequently show 0 items - that's intentional
  (see intro), not a bug. The client-side category filter accounts for
  sparse categories too: it hides any date heading left with zero visible
  items under it, so picking a quiet category doesn't leave a trail of
  empty date labels.
- Translation can occasionally fail on very long text - deep-translator
  raised "No translation was found" once on an unusually long Taiwan Today
  summary during testing. `Translator.translate()` catches this and falls
  back to the original (untranslated) text instead of dropping the article
  - rare, but worth knowing if a single summary shows up not translated.
- Translation is the dominant cost of a cold run. The early per-item date
  check (see "How it works") skips it for anything already outside the
  retention window, but everything inside it still needs up to two
  translation calls (title, summary) - a busy 48-hour news cycle across 29
  sources can still take a few minutes on a fully cold cache.
  `data/translation_cache.json` is saved after every source (not just at
  the end), so an interrupted run doesn't lose that work - re-running
  resumes from a warm cache.
