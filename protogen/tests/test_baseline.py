"""The baseline's output has to be valid before anything downstream matters."""

from __future__ import annotations

import ast

import pytest

from protogen import baseline
from protogen.spec import Entity, Field_, Spec

jinja2 = pytest.importorskip("jinja2")

GENERATORS = ("models_py", "seed_py", "routes_py", "smoke_py")


@pytest.mark.parametrize("generator", GENERATORS)
def test_generated_python_parses(spec, generator):
    source = getattr(baseline, generator)(spec)
    ast.parse(source)


@pytest.mark.parametrize("generator", GENERATORS)
def test_generated_python_survives_an_empty_spec(generator):
    # A spec with no entities is reachable (an intake that found nothing
    # concrete) and must not produce a file that fails to import.
    empty = Spec(name="Empty", slug="empty", purpose="nothing yet")
    ast.parse(getattr(baseline, generator)(empty))


def test_generated_templates_parse(spec):
    env = jinja2.Environment()
    for path, body in baseline.templates_for(spec).items():
        env.parse(body), path


def test_every_field_type_is_supported_everywhere():
    """Four separate tables have to agree, or a tree fails at a different
    stage depending on which type the user's idea happened to need."""
    from protogen.spec import FieldType

    types = set(FieldType.__args__)
    assert types <= set(baseline.TYPES)
    for type_name in types:
        field = Field_(name="sample", type=type_name)
        assert baseline.seed_expr(field)
        assert baseline._input(field)
        assert baseline._set_value(field)
        assert type_name in baseline._FORM_VALUES


def test_child_model_gets_a_foreign_key_and_both_relationship_sides(spec):
    source = baseline.models_py(spec)
    assert 'ForeignKey("trips.id")' in source
    assert 'back_populates="items"' in source
    assert 'back_populates="trip"' in source
    assert 'cascade="all, delete-orphan"' in source


def test_seed_inserts_parents_before_children(spec):
    source = baseline.seed_py(spec)
    assert source.index("trip_rows = []") < source.index("item_rows = []")
    # flush before the children so parent.id exists to reference
    assert source.index("db.flush()") < source.index("for parent in trip_rows:")


def test_seed_is_guarded(spec):
    assert "if db.scalar(select(Trip).limit(1)) is not None:" in baseline.seed_py(spec)


def test_routes_redirect_with_303(spec):
    # 307 replays the POST on the redirect target and double-creates the row.
    source = baseline.routes_py(spec)
    assert "status_code=303" in source
    assert "status_code=307" not in source


def test_required_fields_get_a_coercion_fallback(spec):
    source = baseline.routes_py(spec)
    assert 'parse_date(form.get("starts_on"), date.today())' in source
    # optional fields get no fallback -- None is a legitimate value for them
    assert 'parse_float(form.get("weight_kg"))' in source


def test_standard_screens_cover_every_entity(spec):
    paths = {s["path"] for s in baseline.standard_screens(spec)}
    assert "/" in paths
    for entity in spec.entities:
        assert f"/{entity.plural}" in paths
        assert f"/{entity.plural}/new" in paths
        assert f"/{entity.plural}/{{row_id}}" in paths
