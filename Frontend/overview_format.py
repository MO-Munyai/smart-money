"""
Pure helpers that turn a GET /instruments/{ticker}/overview payload into
display-ready pieces for pages/Instrument_Overview.py (7.1.5).

Kept out of the page so they can be unit-tested without Streamlit. The core
rule (user requirement): a field that is null/empty is HIDDEN, never shown as
"N/A" - so every builder here simply drops anything without a real value.
"""
from datetime import date

SUMMARY_PREVIEW_CHARS = 600
# A summary only slightly over the preview length is shown whole: an expander
# holding one trailing sentence is more annoying than just showing the text.
SUMMARY_TOLERANCE_CHARS = 300


def has_value(value):
    """True for anything worth showing: not None, not blank, not an empty collection."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compact_number(value):
    """3_000_000_000_000 -> '3.00T', 539_134_230_528 -> '539.13B', 45_780 -> '45,780'."""
    if not _is_number(value):
        return None
    magnitude = abs(value)
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if magnitude >= threshold:
            return f"{value / threshold:.2f}{suffix}"
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"


def format_count(value):
    """164000 -> '164,000'. Non-numbers return None so the field is hidden."""
    if not _is_number(value):
        return None
    return f"{value:,.0f}"


def format_price(value):
    if not _is_number(value):
        return None
    return f"{value:,.2f}"


def format_date(iso_value):
    """'1993-01-22' -> '22 Jan 1993'. Anything unparseable returns None (hidden)."""
    if not isinstance(iso_value, str):
        return None
    try:
        parsed = date.fromisoformat(iso_value)
    except ValueError:
        return None
    return f"{parsed.day} {parsed:%b %Y}"


def split_summary(text, limit=SUMMARY_PREVIEW_CHARS, tolerance=SUMMARY_TOLERANCE_CHARS):
    """
    Returns (preview, remainder). A summary within `limit` comes back whole
    with remainder None, as does one within `tolerance` characters over it.
    A longer one is cut at the last sentence end before the limit (or the last
    space if there is none), and the rest is returned so the page can tuck it
    into an expander instead of duplicating text.
    """
    if not has_value(text):
        return None, None
    text = text.strip()
    if len(text) <= limit + tolerance:
        return text, None

    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    cut = cut + 1 if cut > limit // 3 else window.rfind(" ")
    if cut <= 0:
        cut = limit
    return text[:cut].strip(), text[cut:].strip()


def _headquarters(details):
    parts = [details.get(k) for k in ("address", "city", "state", "zip", "country")]
    parts = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return ", ".join(parts) if parts else None


def build_facts(overview):
    """
    Ordered (label, value) pairs for the key-facts grid, by instrument type.
    Only facts with a real value are returned.
    """
    details = overview.get("details") or {}
    instrument_type = overview.get("type")

    if instrument_type == "Stock":
        candidates = [
            ("Sector", details.get("sector")),
            ("Industry", details.get("industry")),
            ("Employees", format_count(details.get("employees"))),
            ("Market cap", compact_number(details.get("market_cap"))),
            ("Headquarters", _headquarters(details)),
            ("Phone", details.get("phone")),
        ]
    elif instrument_type == "ETF":
        candidates = [
            ("Fund family", details.get("fund_family")),
            ("Category", details.get("category")),
            ("Legal type", details.get("legal_type")),
            ("Inception", format_date(details.get("inception_date"))),
            ("Total assets", compact_number(details.get("total_assets"))),
            ("NAV price", format_price(details.get("nav_price"))),
        ]
    elif instrument_type == "Crypto":
        candidates = [
            ("Circulating supply", compact_number(details.get("circulating_supply"))),
            ("Market cap", compact_number(details.get("market_cap"))),
            ("Launched", format_date(details.get("launch_date"))),
        ]
    else:
        candidates = []

    return [(label, value) for label, value in candidates if has_value(value)]


def build_links(overview):
    """(label, url) pairs for the website links that actually exist."""
    details = overview.get("details") or {}
    candidates = [
        ("Website", overview.get("website")),
        ("Investor relations", details.get("ir_website")),
    ]
    return [(label, url) for label, url in candidates if has_value(url)]


def build_officers(overview):
    """
    Officer rows with a name; titles may be missing. Key order is the display
    column order: Title first, then Name.
    """
    officers = (overview.get("details") or {}).get("officers") or []
    return [
        {"Title": o.get("title") or "", "Name": o["name"]}
        for o in officers
        if isinstance(o, dict) and has_value(o.get("name"))
    ]


def empty_profile_message(overview):
    """
    Whole-page fallback for when there is nothing to show beyond the header
    (e.g. an index: Yahoo provides name/exchange/currency only).
    """
    instrument_type = overview.get("type")
    if instrument_type == "Index":
        return "Yahoo Finance doesn't provide a description or profile details for indices."
    if instrument_type:
        return f"Yahoo Finance has no profile details for this {instrument_type.lower()}."
    return "Yahoo Finance has no profile details for this instrument."


def is_empty_profile(overview):
    return not (
        has_value(overview.get("summary"))
        or build_facts(overview)
        or build_links(overview)
        or build_officers(overview)
    )
