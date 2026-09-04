from gaming_buddy.tags import MAX_TAGS_PER_CARD, format_tags, normalize_tags


def test_normalize_tags_trims_deduplicates_and_accepts_semicolons() -> None:
    assert normalize_tags(" Map, boss ; MAP, #safe   code, ") == (
        "Map",
        "boss",
        "safe code",
    )


def test_normalize_tags_enforces_card_limit() -> None:
    values = [f"tag-{index}" for index in range(MAX_TAGS_PER_CARD + 4)]

    assert normalize_tags(values) == tuple(values[:MAX_TAGS_PER_CARD])


def test_format_tags_adds_readable_prefixes() -> None:
    assert format_tags(("map", "boss")) == "#map  #boss"
