"""slug: identity derivation must be deterministic and idempotent."""

from markov_protocols import slugify


def test_slug_lowercases_and_collapses_space_and_punctuation() -> None:
    assert slugify("Collect Customer Data") == "collect-customer-data"
    assert slugify("  Send   Confirmation!! ") == "send-confirmation"


def test_slug_is_idempotent() -> None:
    for title in ["Collect Customer Data", "A/B Test", "weird  __  name"]:
        assert slugify(slugify(title)) == slugify(title)


def test_slug_is_empty_without_alphanumerics() -> None:
    # Callers treat an empty slug as an invalid title.
    assert slugify("***") == ""
