"""
Configuration for the Taiwan News Feed aggregator.

Every source below was individually verified (July 2026) to:
  1. return a real, parseable RSS/Atom feed (not an HTML shell or 404), and
  2. carry genuine, current publish dates on its items - not a static
     archive dump with no date metadata.

That second point mattered a lot: an earlier version of this project used
MOFA's Chinese "OpenData" feeds, which return items with NO date field at
all (not even a bozo/malformed one - just absent). Every item silently fell
back to "now," so a random years-old press item could appear at the top of
the ticker looking like breaking news. Those feeds were dropped in favor of
MOFA's own English feeds, which do carry a proper <pubDate> per item - see
"Sources that were dropped" in README.md for the full list of what got cut
and why.

To add a new RSS source, append an entry to FEEDS below. See README.md for
a full walkthrough with examples.
"""

# ---------------------------------------------------------------------------
# Source categories & colors (used for the badges in index.html)
# ---------------------------------------------------------------------------
CATEGORY_STYLES = {
    "government": {
        "label": "Official / Government",
        "icon": "\U0001F3DB️",  # classical building
        "color": "#c9a227",
        "text_color": "#1a1400",
    },
    "wire_zh": {
        "label": "CNA Wire (Chinese, translated)",
        "icon": "\U0001F4E1",  # satellite antenna
        "color": "#c0392b",
        "text_color": "#ffffff",
    },
    "wire_en": {
        "label": "CNA Wire (Focus Taiwan, English)",
        "icon": "\U0001F4E1",  # satellite antenna
        "color": "#e67e22",
        "text_color": "#1a1400",
    },
    "press_zh": {
        "label": "Taiwan Press (Chinese, translated)",
        "icon": "\U0001F4F0",  # newspaper
        "color": "#27ae60",
        "text_color": "#ffffff",
    },
    "press_en": {
        "label": "Taiwan Press (English)",
        "icon": "\U0001F4F0",  # newspaper
        "color": "#2980b9",
        "text_color": "#ffffff",
    },
    "culture": {
        "label": "Culture",
        "icon": "\U0001F3AD",  # performing arts masks
        "color": "#d35400",
        "text_color": "#ffffff",
    },
    "analysis": {
        "label": "Policy / Academic Analysis",
        "icon": "\U0001F4DA",  # books
        "color": "#16a085",
        "text_color": "#ffffff",
    },
}

# ---------------------------------------------------------------------------
# RSS sources
#
# Fields:
#   name      - display name shown as the source badge/link
#   url       - RSS/Atom feed URL
#   category  - one of the keys in CATEGORY_STYLES
#   lang      - the feed's source language, matched against
#               GOOGLE_SOURCE_LANG in fetch_news.py: "zh" for Traditional
#               Chinese (pinned to zh-TW), "en" for English (no
#               translation).
#   always_relevant - optional, default False. Set True to skip the KEYWORDS
#               filter entirely (use for sources that are inherently on-topic
#               end-to-end, e.g. a foreign ministry's own press releases, or
#               a magazine whose entire scope is Taiwan politics/culture).
# ---------------------------------------------------------------------------
FEEDS = [
    # --- Official government sources (English, dated, always on-topic) ----
    {
        "name": "MOFA Taiwan - News & Events",
        "url": "https://en.mofa.gov.tw/OpenData.aspx?SN=07564A7F01D47BAD",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    {
        "name": "MOFA Taiwan - Press Releases",
        "url": "https://en.mofa.gov.tw/OpenData.aspx?SN=3273AA376FB01416",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    {
        "name": "MOFA Taiwan - Statements & Responses",
        "url": "https://en.mofa.gov.tw/OpenData.aspx?SN=E57623EED610E7DF",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    {
        "name": "MOFA Taiwan - Background Information",
        "url": "https://en.mofa.gov.tw/OpenData.aspx?SN=1AB31BB323796045",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    {
        "name": "MOFA Taiwan - Important Remarks",
        "url": "https://en.mofa.gov.tw/OpenData.aspx?SN=324AD193C0683D72",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    {
        "name": "Office of the President - News",
        "url": "https://english.president.gov.tw/RSSNEWS.aspx",
        "category": "government",
        "lang": "en",
        "always_relevant": True,
    },
    # --- CNA / 中央通訊社 (Taiwan's national wire service) - Chinese,
    # translated per project requirements. Trimmed to the sections that are
    # actually politics/diplomacy/cross-strait/culture; the wire's finance,
    # tech, sports, lifestyle and entertainment sections were dropped since
    # they're out of scope for this ticker. ----------------------------
    {
        "name": "CNA - Politics",
        "url": "https://feeds.feedburner.com/rsscna/politics",
        "category": "wire_zh",
        "lang": "zh",
    },
    {
        "name": "CNA - International",
        "url": "https://feeds.feedburner.com/rsscna/intworld",
        "category": "wire_zh",
        "lang": "zh",
    },
    {
        "name": "CNA - Cross-Strait",
        "url": "https://feeds.feedburner.com/rsscna/mainland",
        "category": "wire_zh",
        "lang": "zh",
    },
    {
        "name": "CNA - Culture",
        "url": "https://feeds.feedburner.com/rsscna/culture",
        "category": "wire_zh",
        "lang": "zh",
    },
    # --- Focus Taiwan - CNA's own English-language news desk. Distinct,
    # separately written English coverage (not a machine translation of the
    # Chinese wire above), so it's kept as its own source/category. -------
    {
        "name": "Focus Taiwan (CNA English News)",
        "url": "https://feeds.feedburner.com/rsscna/engnews/",
        "category": "wire_en",
        "lang": "en",
    },
    # --- Taiwan press (Chinese language, translated) - Liberty Times'
    # section feeds, not their unfiltered "all news" firehose. -------------
    {
        "name": "Liberty Times - Politics",
        "url": "https://news.ltn.com.tw/rss/politics.xml",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "Liberty Times - International",
        "url": "https://news.ltn.com.tw/rss/world.xml",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "Liberty Times - Arts & Culture",
        "url": "https://news.ltn.com.tw/rss/art.xml",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "Liberty Times - Military & Defense",
        "url": "https://news.ltn.com.tw/rss/def.xml",
        "category": "press_zh",
        "lang": "zh",
    },
    # --- Storm Media (風傳媒) - section feeds, very high update frequency
    # (often multiple items per hour), which matters a lot for a 48h-window
    # ticker. -------------------------------------------------------------
    {
        "name": "Storm Media - Politics",
        "url": "https://www.storm.mg/api/getRss/channel_id/7?path=https%3A%2F%2Fwww.storm.mg%2Farticle",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "Storm Media - International",
        "url": "https://www.storm.mg/api/getRss/channel_id/10?path=https%3A%2F%2Fwww.storm.mg%2Farticle",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "Storm Media - Cross-Strait",
        "url": "https://www.storm.mg/api/getRss/channel_id/11?path=https%3A%2F%2Fwww.storm.mg%2Farticle",
        "category": "press_zh",
        "lang": "zh",
    },
    # --- ETtoday - section feeds, also very high frequency. --------------
    {
        "name": "ETtoday - Politics",
        "url": "https://feeds.feedburner.com/ettoday/news",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "ETtoday - International",
        "url": "https://feeds.feedburner.com/ettoday/global",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "ETtoday - Cross-Strait",
        "url": "https://feeds.feedburner.com/ettoday/china",
        "category": "press_zh",
        "lang": "zh",
    },
    {
        "name": "ETtoday - Military & Defense",
        "url": "https://feeds.feedburner.com/ettoday/army",
        "category": "press_zh",
        "lang": "zh",
    },
    # --- The News Lens (關鍵評論網) - general feed (no section split found),
    # so it relies on KEYWORDS filtering like the other non-always_relevant
    # sources. -------------------------------------------------------------
    {
        "name": "The News Lens",
        "url": "https://feeds.feedburner.com/TheNewsLens",
        "category": "press_zh",
        "lang": "zh",
    },
    # --- Taiwan press (English language) --------------------------------
    {
        "name": "Taipei Times",
        "url": "https://www.taipeitimes.com/xml/index.rss",
        "category": "press_en",
        "lang": "en",
    },
    {
        "name": "Taiwan Today",
        "url": "https://api.taiwantoday.tw/en/rss.php?unit=2,6,10,15,18",
        "category": "press_en",
        "lang": "en",
    },
    # --- Culture -----------------------------------------------------------
    {
        # Taiwan Today's culture-magazine units (Taiwan Review / Culture
        # Weekly Wrap style long-form features - arts, heritage, festivals),
        # as opposed to the Top News mix in the "Taiwan Today" feed above.
        # Updates in batches (a monthly issue lands with one shared pubDate)
        # rather than continuously - that's normal for this source.
        "name": "Taiwan Today - Culture",
        "url": "https://api.taiwantoday.tw/en/rss.php?unit=4,8,12,14,20",
        "category": "culture",
        "lang": "en",
        "always_relevant": True,
    },
    # --- Policy / academic analysis ---------------------------------------
    {
        "name": "Taiwan Insight (Taiwan Research Hub, U. Nottingham)",
        "url": "https://taiwaninsight.org/feed/",
        "category": "analysis",
        "lang": "en",
        "always_relevant": True,  # entire publication is Taiwan politics/culture
    },
    {
        "name": "Global Taiwan Brief (Global Taiwan Institute)",
        "url": "https://globaltaiwan.org/feed/",
        "category": "analysis",
        "lang": "en",
        "always_relevant": True,  # entire publication is Taiwan/US policy analysis
    },
    {
        "name": "The Diplomat - Taiwan",
        "url": "https://thediplomat.com/tag/taiwan/feed/",
        "category": "analysis",
        "lang": "en",
        "always_relevant": True,  # already scoped to the "Taiwan" tag
    },
]

# ---------------------------------------------------------------------------
# Relevance keywords (matched with word-boundaries, case-insensitively,
# against the English title/summary, i.e. after translation). An item is
# kept if at least one keyword matches. This only applies to sources
# without always_relevant=True - it's what narrows Taiwan Today, Taipei
# Times, CNA, Liberty Times, Storm Media, ETtoday and The News Lens down to
# items that actually relate to Taiwanese politics, diplomacy, culture and
# international relations.
#
# NOTE: bare geographic/identity terms like "taiwan" or "taipei" are
# deliberately NOT in this list. Nearly every headline from a Taiwan-based
# outlet mentions Taiwan somewhere, even for tax, health or sports stories -
# so including them here would defeat the filter and let everything through.
# ---------------------------------------------------------------------------
KEYWORDS = [
    # Cross-strait & mainland relations
    "cross-strait", "cross strait", "mainland china", "beijing", "prc",
    "unification", "reunification", "one china", "taiwan strait",
    "taiwan independence", "annexation", "status quo",
    # Government / politics
    "president lai", "lai ching-te", "tsai ing-wen", "vice president",
    "legislative yuan", "executive yuan", "premier", "cabinet reshuffle",
    "dpp", "democratic progressive party", "kmt", "kuomintang",
    "tpp", "taiwan people's party", "referendum", "by-election",
    "legislator", "recall vote", "constitutional court", "election",
    "elections", "electoral", "lawmaker", "parliament", "ruling party",
    "opposition party", "political party", "cabinet", "premier su",
    "head of state", "self-determination",
    # Diplomacy / foreign relations
    "diplomacy", "diplomatic", "diplomatic ally", "diplomatic allies",
    "foreign minister", "foreign ministry", "mofa", "ambassador",
    "embassy", "consulate", "bilateral", "multilateral", "summit",
    "state visit", "official visit", "sanctions", "treaty",
    "trade agreement", "trade deal", "tariff", "foreign policy",
    "diplomatic relations", "recognizes taiwan", "severs ties",
    # International relations / security
    "united states", "us-taiwan", "u.s.-taiwan", "washington",
    "arms sale", "arms deal", "military drill", "pla", "plaaf",
    "adiz", "incursion", "air defense identification zone",
    "south china sea", "indo-pacific", "asean", "united nations",
    "world health organization", "g7", "european union",
    "japan-taiwan", "australia-taiwan", "sovereignty", "self-ruled",
    "self-governing island", "island nation", "geopolitics",
    "semiconductor export", "chip war", "tsmc policy", "defense ministry",
    "defense minister", "national security", "invasion", "blockade",
    "war games", "grey zone", "gray zone", "espionage", "sabotage",
    "united front", "human rights", "sovereign state", "statehood",
    # Culture (Taiwanese identity, heritage & cross-strait cultural affairs)
    "indigenous", "aboriginal", "heritage", "identity", "censorship",
    "freedom of the press", "academia sinica", "ministry of culture",
]
