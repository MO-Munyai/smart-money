import overview_format as f


# --- has_value ---

def test_has_value_hides_none_blank_and_empty_collections():
    assert not f.has_value(None)
    assert not f.has_value("")
    assert not f.has_value("   ")
    assert not f.has_value([])
    assert not f.has_value({})


def test_has_value_keeps_real_values_including_zero_and_false():
    assert f.has_value("x")
    assert f.has_value(0)
    assert f.has_value(False)
    assert f.has_value(["a"])


# --- number / date formatting ---

def test_compact_number_scales_and_suffixes():
    assert f.compact_number(3_000_000_000_000) == "3.00T"
    assert f.compact_number(539_134_230_528) == "539.13B"
    assert f.compact_number(20_098_844) == "20.10M"
    assert f.compact_number(45_780) == "45,780"
    assert f.compact_number(12.5) == "12.50"


def test_compact_number_rejects_non_numbers():
    assert f.compact_number(None) is None
    assert f.compact_number("5") is None
    assert f.compact_number(True) is None


def test_format_count_and_price():
    assert f.format_count(164000) == "164,000"
    assert f.format_count("164000") is None
    assert f.format_price(771.8012) == "771.80"
    assert f.format_price(None) is None


def test_format_date():
    assert f.format_date("1993-01-22") == "22 Jan 1993"
    assert f.format_date("2010-07-03") == "3 Jul 2010"
    assert f.format_date("not a date") is None
    assert f.format_date(None) is None
    assert f.format_date(1278979200) is None


# --- split_summary ---

def test_split_summary_short_text_returned_whole():
    assert f.split_summary("Short text.") == ("Short text.", None)


def test_split_summary_slightly_over_the_limit_is_still_shown_whole():
    text = "word " * 130  # ~650 chars: over 600 but within the 300 tolerance
    preview, rest = f.split_summary(text.strip())
    assert rest is None
    assert preview == text.strip()


def test_split_summary_well_over_the_limit_is_split():
    preview, rest = f.split_summary(("word " * 250).strip())  # ~1250 chars
    assert rest
    assert len(preview) <= f.SUMMARY_PREVIEW_CHARS


def test_split_summary_missing_or_blank_is_none():
    assert f.split_summary(None) == (None, None)
    assert f.split_summary("   ") == (None, None)


def test_split_summary_long_text_cuts_at_a_sentence_end():
    sentence = "This is a sentence of reasonable length for testing. "
    text = sentence * 30
    preview, rest = f.split_summary(text, limit=200)

    assert preview.endswith(".")
    assert len(preview) <= 200
    assert rest
    assert (preview + " " + rest).split() == text.split()


def test_split_summary_without_sentence_ends_cuts_at_a_space():
    text = "word " * 100
    preview, rest = f.split_summary(text, limit=50)

    assert len(preview) <= 50
    assert not preview.endswith("wor")
    assert (preview + " " + rest).split() == text.split()


def test_split_summary_unbroken_text_still_splits_at_the_limit():
    preview, rest = f.split_summary("x" * 1000, limit=100)
    assert len(preview) == 100
    assert len(rest) == 900


# --- build_facts ---

STOCK = {
    "type": "Stock", "website": "https://apple.com",
    "details": {
        "sector": "Technology", "industry": "Consumer Electronics", "employees": 164000,
        "market_cap": 3e12, "address": "One Apple Park Way", "city": "Cupertino",
        "state": "CA", "zip": "95014", "country": "United States",
        "phone": "1 408 996 1010", "ir_website": "https://investor.apple.com",
        "officers": [{"name": "Tim Cook", "title": "CEO"}],
    },
}


def test_stock_facts_are_ordered_and_formatted():
    assert f.build_facts(STOCK) == [
        ("Sector", "Technology"),
        ("Industry", "Consumer Electronics"),
        ("Employees", "164,000"),
        ("Market cap", "3.00T"),
        ("Headquarters", "One Apple Park Way, Cupertino, CA, 95014, United States"),
        ("Phone", "1 408 996 1010"),
    ]


def test_stock_facts_hide_missing_fields_entirely():
    """NPN.JO-style: no state, no phone, no employees."""
    overview = {"type": "Stock", "details": {
        "sector": "Consumer Cyclical", "city": "Cape Town", "state": None,
        "country": "South Africa", "employees": None, "phone": "",
    }}
    facts = dict(f.build_facts(overview))

    assert facts == {"Sector": "Consumer Cyclical", "Headquarters": "Cape Town, South Africa"}


def test_headquarters_hidden_when_no_address_parts():
    assert "Headquarters" not in dict(f.build_facts({"type": "Stock", "details": {"sector": "X"}}))


def test_etf_facts():
    overview = {"type": "ETF", "details": {
        "fund_family": "State Street", "category": "Large Blend",
        "legal_type": "Exchange Traded Fund", "inception_date": "1993-01-22",
        "total_assets": 8.09e11, "nav_price": 771.8012,
    }}
    assert f.build_facts(overview) == [
        ("Fund family", "State Street"), ("Category", "Large Blend"),
        ("Legal type", "Exchange Traded Fund"), ("Inception", "22 Jan 1993"),
        ("Total assets", "809.00B"), ("NAV price", "771.80"),
    ]


def test_crypto_facts():
    overview = {"type": "Crypto", "details": {
        "circulating_supply": 20_098_844, "market_cap": 1.64e12, "launch_date": "2010-07-13",
    }}
    assert f.build_facts(overview) == [
        ("Circulating supply", "20.10M"), ("Market cap", "1.64T"), ("Launched", "13 Jul 2010"),
    ]


def test_index_and_unknown_types_have_no_facts():
    assert f.build_facts({"type": "Index", "details": {}}) == []
    assert f.build_facts({"type": None, "details": {"sector": "X"}}) == []
    assert f.build_facts({"type": "Stock"}) == []


# --- build_links / build_officers ---

def test_links_include_only_existing_urls():
    assert f.build_links(STOCK) == [
        ("Website", "https://apple.com"), ("Investor relations", "https://investor.apple.com"),
    ]
    assert f.build_links({"website": None, "details": {"ir_website": ""}}) == []
    assert f.build_links({"website": "https://x.org", "details": {}}) == [("Website", "https://x.org")]


def test_officers_drop_nameless_and_blank_titles_become_empty():
    overview = {"details": {"officers": [
        {"name": "A", "title": "CEO"}, {"name": "B", "title": None}, {"title": "no name"}, "junk",
    ]}}
    assert f.build_officers(overview) == [
        {"Name": "A", "Title": "CEO"}, {"Name": "B", "Title": ""},
    ]


def test_officers_missing_is_empty_list():
    assert f.build_officers({}) == []
    assert f.build_officers({"details": {}}) == []


# --- empty-profile fallback ---

def test_index_with_nothing_is_an_empty_profile_with_specific_message():
    index = {"type": "Index", "summary": None, "website": None, "details": {}}
    assert f.is_empty_profile(index)
    assert "indices" in f.empty_profile_message(index)


def test_message_names_the_type_or_falls_back_generically():
    assert "crypto" in f.empty_profile_message({"type": "Crypto"})
    assert "this instrument" in f.empty_profile_message({"type": None})


def test_profile_with_only_a_summary_is_not_empty():
    assert not f.is_empty_profile({"type": "Index", "summary": "Hello", "details": {}})


def test_profile_with_only_officers_or_links_is_not_empty():
    assert not f.is_empty_profile({"type": "Stock", "details": {"officers": [{"name": "A"}]}})
    assert not f.is_empty_profile({"type": "Crypto", "website": "https://x.org", "details": {}})
