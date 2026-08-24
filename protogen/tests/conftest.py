from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protogen.spec import Entity, Field_, Spec  # noqa: E402


@pytest.fixture()
def spec() -> Spec:
    """Two entities, a parent/child relationship, and every field type.

    Every type is present on purpose: the column mapping, the form input, the
    coercion helper and the seed literal are four separate tables in
    baseline.py, and a type missing from any one of them produces a tree that
    fails at a different stage each time.
    """
    return Spec(
        name="Gear List",
        slug="gearlist",
        purpose="Track camping gear across trips.",
        port=8099,
        entities=[
            Entity(
                name="Trip",
                fields=[
                    Field_(name="title", type="str"),
                    Field_(name="starts_on", type="date"),
                    Field_(name="notes", type="text", required=False),
                    Field_(name="nights", type="int", required=False),
                ],
            ),
            Entity(
                name="Item",
                belongs_to="Trip",
                fields=[
                    Field_(name="name", type="str"),
                    Field_(name="packed", type="bool", required=False),
                    Field_(name="weight_kg", type="float", required=False),
                    Field_(name="checked_at", type="datetime", required=False),
                ],
            ),
        ],
    )
