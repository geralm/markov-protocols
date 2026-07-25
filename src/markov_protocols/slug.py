"""Deterministic slug derivation.

A state's ``id`` is the slug of its ``title``. Slugging must be deterministic and
idempotent so the same title always yields the same id — that is what makes the
graph's identity stable and its transitions referenceable.
"""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Lowercase, collapse every run of non-alphanumerics to a single hyphen.

    Idempotent: ``slugify(slugify(x)) == slugify(x)``. Returns ``""`` when the
    title has no alphanumeric content — callers treat that as invalid.
    """
    return _NON_ALNUM.sub("-", title.strip().lower()).strip("-")
