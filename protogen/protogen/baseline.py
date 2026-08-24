"""The deterministic baseline generator.

Every pass has two implementations: a prompt, and one of these. The baseline
is what `--offline` runs, what protogen's own test suite runs, and what the
prompts are written against -- a pass whose prompt asks for something the
baseline cannot express is a pass with no worked example, and it shows.

It produces a plain CRUD app. That is not the interesting output; it is the
floor, and having a floor is what lets the interesting output be checked.
"""

from __future__ import annotations

from dataclasses import dataclass

from protogen.spec import Entity, Field_, Spec


@dataclass(frozen=True)
class TypeInfo:
    sa: str  # SQLAlchemy column type expression
    py: str  # Python annotation inside Mapped[...]
    parse: str  # helper in app.forms
    fallback: str  # value used when a *required* field arrives empty


TYPES: dict[str, TypeInfo] = {
    "str": TypeInfo("String(255)", "str", "parse_str", ""),
    "text": TypeInfo("Text", "str", "parse_str", ""),
    "int": TypeInfo("Integer", "int", "parse_int", "0"),
    "float": TypeInfo("Float", "float", "parse_float", "0.0"),
    "bool": TypeInfo("Boolean", "bool", "parse_bool", ""),
    "date": TypeInfo("Date", "date", "parse_date", "date.today()"),
    "datetime": TypeInfo("DateTime", "datetime", "parse_datetime", "datetime.now()"),
}


def seed_expr(field: Field_) -> str:
    """A Python expression, evaluated inside the seed's `for i in ...` loop.

    Deterministic so a regenerated seed is a no-op diff, and varying with `i`
    so the prototype demos with a table rather than five identical rows.
    """
    label = field.human_label()
    lower = label.lower()
    return {
        "str": 'f"' + label + ' {i}"',
        "text": 'f"Notes on ' + lower + " {i}. Replace this with something real.\"",
        "int": "i * 3",
        "float": "round(i * 2.5, 2)",
        "bool": "i % 2 == 0",
        "date": "date.today() + timedelta(days=i * 3)",
        "datetime": "datetime.now() + timedelta(hours=i * 5)",
    }[field.type]


def _blocks(header: list[str], blocks: list[str]) -> str:
    """Join top-level definitions with exactly two blank lines between them."""
    body = "\n\n\n".join(b.rstrip("\n") for b in blocks if b.strip())
    head = "\n".join(header).rstrip("\n")
    if not body:
        return head + "\n"
    return head + "\n\n\n" + body + "\n"


def children_of(spec: Spec, entity: Entity) -> list[Entity]:
    return [e for e in spec.entities if e.belongs_to == entity.name]


def ordered_entities(spec: Spec) -> list[Entity]:
    """Parents before children -- a child row needs its parent's id to exist."""
    return [e for e in spec.entities if not e.belongs_to] + [
        e for e in spec.entities if e.belongs_to
    ]


# -- models ------------------------------------------------------------


def models_py(spec: Spec) -> str:
    header = [
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime  # noqa: F401",
        "from typing import Optional",
        "",
        "from sqlalchemy import (",
        "    Boolean,",
        "    Date,",
        "    DateTime,",
        "    Float,",
        "    ForeignKey,",
        "    Integer,",
        "    String,",
        "    Text,",
        ")",
        "from sqlalchemy.orm import Mapped, mapped_column, relationship",
        "",
        "from app.db import Base",
    ]
    blocks: list[str] = []
    for entity in spec.entities:
        lines = [f"class {entity.name}(Base):", f'    __tablename__ = "{entity.table}"', ""]
        lines.append("    id: Mapped[int] = mapped_column(primary_key=True)")
        for field in entity.fields:
            info = TYPES[field.type]
            ann = info.py if field.required else f"Optional[{info.py}]"
            null = "False" if field.required else "True"
            lines.append(
                f"    {field.name}: Mapped[{ann}] = "
                f"mapped_column({info.sa}, nullable={null})"
            )
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None, f"unknown parent {entity.belongs_to!r}"
            lines.append(
                f"    {parent.var}_id: Mapped[Optional[int]] = "
                f'mapped_column(ForeignKey("{parent.table}.id"))'
            )
            lines.append(
                f'    {parent.var}: Mapped[Optional["{parent.name}"]] = '
                f'relationship(back_populates="{entity.plural}")'
            )
        for child in children_of(spec, entity):
            lines += [
                f'    {child.plural}: Mapped[list["{child.name}"]] = relationship(',
                f'        back_populates="{entity.var}",',
                # Deleting a parent should not leave orphans that every later
                # query has to filter out.
                '        cascade="all, delete-orphan",',
                "    )",
            ]
        lines += [
            "",
            "    @property",
            "    def display(self) -> str:",
            '        """Short label for tables, links and page titles."""',
            f"        return {_display_expr(entity)}",
            "",
            "    def __str__(self) -> str:",
            "        return self.display",
        ]
        blocks.append("\n".join(lines))
    return _blocks(header, blocks)


def _display_expr(entity: Entity) -> str:
    for field in entity.fields:
        if field.type in {"str", "text"}:
            return f'str(self.{field.name} or "") or f"{entity.name} {{self.id}}"'
    return f'f"{entity.name} {{self.id}}"'


# -- seed --------------------------------------------------------------


def seed_py(spec: Spec, rows: int = 5) -> str:
    header = [
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime, timedelta  # noqa: F401",
        "",
        "from sqlalchemy import select",
        "from sqlalchemy.orm import Session",
    ]
    if spec.entities:
        names = ", ".join(e.name for e in spec.entities)
        header += ["", f"from app.models import {names}"]

    body = [
        "def seed(db: Session) -> None:",
        '    """Idempotent. lifespan runs on every reload, and an unguarded seed',
        '    turns hot reload into a duplicate-row factory."""',
    ]
    if not spec.entities:
        body.append("    return None")
        return _blocks(header, ["\n".join(body)])

    first = spec.entities[0]
    body += [
        f"    if db.scalar(select({first.name}).limit(1)) is not None:",
        "        return None",
        "",
    ]
    made: dict[str, str] = {}
    for entity in ordered_entities(spec):
        var = f"{entity.var}_rows"
        made[entity.name] = var
        body.append(f"    {var} = []")
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            body.append(f"    for parent in {made[parent.name]}:")
            body.append(f"        for i in range(1, {max(2, rows // 2) + 1}):")
            indent = " " * 12
        else:
            body.append(f"    for i in range(1, {rows + 1}):")
            indent = " " * 8
        body.append(f"{indent}row = {entity.name}(")
        for field in entity.fields:
            body.append(f"{indent}    {field.name}={seed_expr(field)},")
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            body.append(f"{indent}    {parent.var}_id=parent.id,")
        body += [
            f"{indent})",
            f"{indent}db.add(row)",
            f"{indent}{var}.append(row)",
            # flush, not commit: children need parent ids, but a failure
            # part-way should roll the whole seed back.
            "    db.flush()",
            "",
        ]
    body.append("    db.commit()")
    return _blocks(header, ["\n".join(body)])


# -- routes ------------------------------------------------------------

_INDEX_ROUTE = '''@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    sections = [
__SECTIONS__
    ]
    return templates.TemplateResponse(request, "index.html", {"sections": sections})'''

_ENTITY_ROUTES = '''@router.get("/__PLURAL__", response_class=HTMLResponse)
def __VAR___list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    rows = db.scalars(select(__NAME__).order_by(__NAME__.id)).all()
    return templates.TemplateResponse(request, "__PLURAL___list.html", {"rows": rows})


@router.get("/__PLURAL__/new", response_class=HTMLResponse)
def __VAR___new(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "__PLURAL___form.html",
        {"obj": None, "action": "/__PLURAL__/new"__PARENTS__},
    )


@router.post("/__PLURAL__/new")
async def __VAR___create(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    form = await request.form()
    row = __NAME__(
__ASSIGN__
    )
    db.add(row)
    db.commit()
    return RedirectResponse(f"/__PLURAL__/{row.id}", status_code=303)


@router.get("/__PLURAL__/{row_id}", response_class=HTMLResponse)
def __VAR___detail(row_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    row = db.get(__NAME__, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="__NAME__ not found")
    return templates.TemplateResponse(request, "__PLURAL___detail.html", {"row": row})


@router.get("/__PLURAL__/{row_id}/edit", response_class=HTMLResponse)
def __VAR___edit(row_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    row = db.get(__NAME__, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="__NAME__ not found")
    return templates.TemplateResponse(
        request,
        "__PLURAL___form.html",
        {"obj": row, "action": f"/__PLURAL__/{row.id}/edit"__PARENTS__},
    )


@router.post("/__PLURAL__/{row_id}/edit")
async def __VAR___update(row_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(__NAME__, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="__NAME__ not found")
    form = await request.form()
__UPDATE__
    db.commit()
    return RedirectResponse(f"/__PLURAL__/{row.id}", status_code=303)


@router.post("/__PLURAL__/{row_id}/delete")
def __VAR___delete(row_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    row = db.get(__NAME__, row_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return RedirectResponse("/__PLURAL__", status_code=303)'''


def _coerce_call(field: Field_) -> str:
    info = TYPES[field.type]
    args = f'form.get("{field.name}")'
    # A required column with an empty submit would otherwise be a 500 from the
    # database rather than a form the user can fix.
    if field.required and info.fallback:
        args += f", {info.fallback}"
    return f"{info.parse}({args})"


def routes_py(spec: Spec) -> str:
    header = [
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime  # noqa: F401",
        "",
        "from fastapi import APIRouter, Depends, HTTPException, Request",
        "from fastapi.responses import HTMLResponse, RedirectResponse",
        "from sqlalchemy import func, select",
        "from sqlalchemy.orm import Session",
        "",
        "from app.db import get_db",
        "from app.forms import (  # noqa: F401",
        "    parse_bool,",
        "    parse_date,",
        "    parse_datetime,",
        "    parse_float,",
        "    parse_int,",
        "    parse_str,",
        ")",
        "from app.templating import templates",
    ]
    if spec.entities:
        header.append(f"from app.models import {', '.join(e.name for e in spec.entities)}")
    header += ["", "router = APIRouter()"]

    sections = []
    for entity in spec.entities:
        sections.append(
            f'        {{"label": "{entity.plural.replace("_", " ").capitalize()}", '
            f'"url": "/{entity.plural}", '
            f'"count": db.scalar(select(func.count()).select_from({entity.name})) or 0}},'
        )
    blocks = [_INDEX_ROUTE.replace("__SECTIONS__", "\n".join(sections))]

    for entity in spec.entities:
        assign, update, parents = [], [], ""
        for field in entity.fields:
            call = _coerce_call(field)
            assign.append(f"        {field.name}={call},")
            update.append(f"    row.{field.name} = {call}")
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            fk = f"{parent.var}_id"
            assign.append(f'        {fk}=parse_int(form.get("{fk}")),')
            update.append(f'    row.{fk} = parse_int(form.get("{fk}"))')
            parents = (
                f', "parents": db.scalars('
                f"select({parent.name}).order_by({parent.name}.id)).all()"
            )
        blocks.append(
            _ENTITY_ROUTES.replace("__NAME__", entity.name)
            .replace("__PLURAL__", entity.plural)
            .replace("__VAR__", entity.var)
            .replace("__ASSIGN__", "\n".join(assign))
            .replace("__UPDATE__", "\n".join(update) or "    pass")
            .replace("__PARENTS__", parents)
        )
    return _blocks(header, blocks)


# -- templates ---------------------------------------------------------
#
# Written with __TOKEN__ markers rather than f-strings or .format(): the
# output is Jinja, which is made of braces, and every brace-escaping scheme
# for generating brace-heavy text eventually produces a template that is
# wrong in a way nobody can read.

_NAV = """<nav>
__LINKS__
</nav>"""

_INDEX = """{% extends "base.html" %}
{% block content %}
  <h1>{{ app_name }}</h1>
  <p class="muted">{{ app_purpose }}</p>
  {% for section in sections %}
  <div class="card">
    <div class="row" style="justify-content: space-between">
      <a href="{{ section.url }}"><strong>{{ section.label }}</strong></a>
      <span class="muted">{{ section.count }}</span>
    </div>
  </div>
  {% endfor %}
{% endblock %}"""

_LIST = """{% extends "base.html" %}
{% block title %}__TITLE__{% endblock %}
{% block content %}
  <div class="row" style="justify-content: space-between">
    <h1>__TITLE__</h1>
    <a class="button" href="/__PLURAL__/new">New __NAME__</a>
  </div>
  {% if rows %}
  <table>
    <thead>
      <tr>
__HEADERS__
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
__CELLS__
        <td><a href="/__PLURAL__/{{ row.id }}">open</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">Nothing here yet. <a href="/__PLURAL__/new">Add the first one</a>.</p>
  {% endif %}
{% endblock %}"""

_DETAIL = """{% extends "base.html" %}
{% block title %}{{ row.display }}{% endblock %}
{% block content %}
  <h1>{{ row.display }}</h1>
__PARENT__
  <div class="card">
    <dl>
__FIELDS__
    </dl>
  </div>
__CHILDREN__
  <div class="row">
    <a class="button secondary" href="/__PLURAL__/{{ row.id }}/edit">Edit</a>
    <form method="post" action="/__PLURAL__/{{ row.id }}/delete">
      <button type="submit">Delete</button>
    </form>
    <a href="/__PLURAL__">Back to __TITLE_LOWER__</a>
  </div>
{% endblock %}"""

_FORM = """{% extends "base.html" %}
{% block title %}{% if obj %}Edit {{ obj.display }}{% else %}New __NAME__{% endif %}{% endblock %}
{% block content %}
  <h1>{% if obj %}Edit {{ obj.display }}{% else %}New __NAME__{% endif %}</h1>
  <form method="post" action="{{ action }}">
__FIELDS__
__PARENT_SELECT__
    <div class="row">
      <button type="submit">Save</button>
      <a class="button secondary" href="/__PLURAL__">Cancel</a>
    </div>
  </form>
{% endblock %}"""

_PARENT_SELECT = """    <label for="__FK__">__PARENT_LABEL__
      {% set value = obj.__FK__ if obj else None %}
      <select name="__FK__" id="__FK__">
        <option value="">--</option>
        {% for parent in parents %}
        <option value="{{ parent.id }}" {% if value == parent.id %}selected{% endif %}>
          {{ parent.display }}
        </option>
        {% endfor %}
      </select>
    </label>"""


def _cell(field: Field_) -> str:
    if field.type == "bool":
        return (
            "        <td>{% if row.__N__ %}yes{% else %}no{% endif %}</td>".replace(
                "__N__", field.name
            )
        )
    return "        <td>{{ row.__N__ }}</td>".replace("__N__", field.name)


def _set_value(field: Field_) -> str:
    """The `{% set value %}` line for one form field.

    date/datetime go through .isoformat() because `<input type="datetime-local">`
    rejects Python's default `2030-01-02 03:04:00` rendering -- it wants the T.
    """
    if field.type in {"date", "datetime"}:
        return (
            "{% set value = obj.__N__.isoformat() if obj and obj.__N__ else '' %}".replace(
                "__N__", field.name
            )
        )
    if field.type == "bool":
        return "{% set value = obj.__N__ if obj else False %}".replace("__N__", field.name)
    return "{% set value = obj.__N__ if obj else '' %}".replace("__N__", field.name)


def _input(field: Field_) -> str:
    n = field.name
    return {
        "str": '<input type="text" name="__N__" id="__N__" value="{{ value }}">',
        "text": '<textarea name="__N__" id="__N__">{{ value }}</textarea>',
        "int": '<input type="number" step="1" name="__N__" id="__N__" value="{{ value }}">',
        "float": '<input type="number" step="any" name="__N__" id="__N__" value="{{ value }}">',
        "bool": '<input type="checkbox" name="__N__" id="__N__" {% if value %}checked{% endif %}>',
        "date": '<input type="date" name="__N__" id="__N__" value="{{ value }}">',
        "datetime": '<input type="datetime-local" name="__N__" id="__N__" value="{{ value }}">',
    }[field.type].replace("__N__", n)


def templates_for(spec: Spec) -> dict[str, str]:
    out: dict[str, str] = {}

    links = "\n".join(
        f'  <a href="/{e.plural}">{e.plural.replace("_", " ").capitalize()}</a>'
        for e in spec.entities
    )
    out["app/templates/_nav.html"] = _NAV.replace("__LINKS__", links or "")
    out["app/templates/index.html"] = _INDEX

    for entity in spec.entities:
        title = entity.plural.replace("_", " ").capitalize()
        base = {
            "__NAME__": entity.name,
            "__PLURAL__": entity.plural,
            "__TITLE__": title,
            "__TITLE_LOWER__": title.lower(),
        }

        headers = "\n".join(
            f"        <th>{f.human_label()}</th>" for f in entity.fields
        )
        cells = "\n".join(_cell(f) for f in entity.fields)
        out[f"app/templates/{entity.plural}_list.html"] = _apply(
            _LIST, base | {"__HEADERS__": headers, "__CELLS__": cells}
        )

        detail_fields = "\n".join(
            f"      <dt class=\"muted\">{f.human_label()}</dt>\n"
            + (
                "      <dd>{% if row.__N__ %}yes{% else %}no{% endif %}</dd>".replace(
                    "__N__", f.name
                )
                if f.type == "bool"
                else "      <dd>{{ row.__N__ }}</dd>".replace("__N__", f.name)
            )
            for f in entity.fields
        )
        parent_block = ""
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            parent_block = (
                "  {% if row.__PVAR__ %}\n"
                '  <p class="muted">Part of '
                '<a href="/__PPLURAL__/{{ row.__PVAR__.id }}">{{ row.__PVAR__.display }}</a></p>\n'
                "  {% endif %}"
            ).replace("__PVAR__", parent.var).replace("__PPLURAL__", parent.plural)

        child_blocks = []
        for child in children_of(spec, entity):
            child_title = child.plural.replace("_", " ").capitalize()
            child_blocks.append(
                (
                    "  <h2>__CTITLE__</h2>\n"
                    "  {% if row.__CPLURAL__ %}\n"
                    "  <ul>\n"
                    "    {% for child in row.__CPLURAL__ %}\n"
                    '    <li><a href="/__CPLURAL__/{{ child.id }}">{{ child.display }}</a></li>\n'
                    "    {% endfor %}\n"
                    "  </ul>\n"
                    "  {% else %}\n"
                    '  <p class="muted">None yet.</p>\n'
                    "  {% endif %}\n"
                    '  <a class="button secondary" href="/__CPLURAL__/new">New __CNAME__</a>'
                )
                .replace("__CPLURAL__", child.plural)
                .replace("__CTITLE__", child_title)
                .replace("__CNAME__", child.name)
            )
        out[f"app/templates/{entity.plural}_detail.html"] = _apply(
            _DETAIL,
            base
            | {
                "__FIELDS__": detail_fields,
                "__PARENT__": parent_block,
                "__CHILDREN__": "\n".join(child_blocks),
            },
        )

        form_fields = "\n".join(
            f"    <label for=\"{f.name}\">{f.human_label()}\n"
            f"      {_set_value(f)}\n"
            f"      {_input(f)}\n"
            "    </label>"
            for f in entity.fields
        )
        parent_select = ""
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            parent_select = _PARENT_SELECT.replace("__FK__", f"{parent.var}_id").replace(
                "__PARENT_LABEL__", parent.name
            )
        out[f"app/templates/{entity.plural}_form.html"] = _apply(
            _FORM, base | {"__FIELDS__": form_fields, "__PARENT_SELECT__": parent_select}
        )

    return {k: v.rstrip("\n") + "\n" for k, v in out.items()}


def _apply(template: str, values: dict[str, str]) -> str:
    for token, value in values.items():
        template = template.replace(token, value)
    return template


# -- smoke tests -------------------------------------------------------

_FORM_VALUES = {
    "str": '"protogen smoke"',
    "text": '"protogen smoke"',
    "int": '"7"',
    "float": '"1.5"',
    "bool": '"on"',
    "date": '"2030-01-02"',
    "datetime": '"2030-01-02T03:04"',
}


def smoke_py(spec: Spec) -> str:
    """Generated from the spec, and generated *before* routes and templates.

    That ordering is the whole point: tests written after the code describe
    whatever the code happened to do. These describe what was asked for, so a
    route the model forgot is a red test rather than a silent omission.
    """
    header = [
        "from __future__ import annotations",
        "",
        "from sqlalchemy import func, select",
    ]
    if spec.entities:
        header += ["", f"from app.models import {', '.join(e.name for e in spec.entities)}"]

    blocks = [
        "def test_index_renders(client) -> None:\n"
        '    response = client.get("/")\n'
        "    assert response.status_code == 200, response.text"
    ]

    for entity in spec.entities:
        p, name, var = entity.plural, entity.name, entity.var
        blocks.append(
            f"def test_{p}_list_renders(client) -> None:\n"
            f'    response = client.get("/{p}")\n'
            "    assert response.status_code == 200, response.text"
        )
        blocks.append(
            f"def test_{var}_is_seeded(db) -> None:\n"
            f'    """A prototype with empty tables cannot be demonstrated."""\n'
            f"    count = db.scalar(select(func.count()).select_from({name}))\n"
            f"    assert count and count > 0"
        )
        blocks.append(
            f"def test_{var}_detail_renders(client, db) -> None:\n"
            f"    row = db.scalars(select({name}).order_by({name}.id).limit(1)).first()\n"
            f'    assert row is not None, "no seeded {name} to open"\n'
            f'    response = client.get(f"/{p}/{{row.id}}")\n'
            "    assert response.status_code == 200, response.text"
        )
        blocks.append(
            f"def test_{var}_new_form_renders(client) -> None:\n"
            f'    response = client.get("/{p}/new")\n'
            "    assert response.status_code == 200, response.text"
        )
        blocks.append(
            f"def test_{var}_unknown_id_is_404(client) -> None:\n"
            f'    assert client.get("/{p}/99999999").status_code == 404'
        )

        data_lines = [
            f'        "{f.name}": {_FORM_VALUES[f.type]},' for f in entity.fields
        ]
        lookup = ""
        if entity.belongs_to:
            parent = spec.entity(entity.belongs_to)
            assert parent is not None
            lookup = (
                f"    parent = db.scalars("
                f"select({parent.name}).order_by({parent.name}.id).limit(1)).first()\n"
                f'    assert parent is not None, "no seeded {parent.name} to attach to"\n'
            )
            data_lines.append(f'        "{parent.var}_id": str(parent.id),')
        blocks.append(
            f"def test_{var}_create_round_trip(client, db) -> None:\n"
            f"    before = db.scalar(select(func.count()).select_from({name}))\n"
            f"{lookup}"
            "    data = {\n" + "\n".join(data_lines) + "\n    }\n"
            f'    response = client.post("/{p}/new", data=data, follow_redirects=True)\n'
            "    assert response.status_code == 200, response.text\n"
            "    # End this session's transaction so the next query sees the\n"
            "    # row the app committed on its own connection.\n"
            "    db.rollback()\n"
            f"    after = db.scalar(select(func.count()).select_from({name}))\n"
            "    assert after == (before or 0) + 1"
        )
    return _blocks(header, blocks)


# -- screens -----------------------------------------------------------


def standard_screens(spec: Spec) -> list[dict]:
    """The CRUD screen set every generated app has.

    Screens are the contract the smoke pass tests and the routes pass must
    satisfy, so they need a predictable shape. A model free to invent URL
    conventions per app produces tests and routes that disagree.
    """
    screens: list[dict] = [
        {"name": "Home", "path": "/", "entity": None, "kind": "custom"}
    ]
    for entity in spec.entities:
        title = entity.plural.replace("_", " ").capitalize()
        screens += [
            {
                "name": title,
                "path": f"/{entity.plural}",
                "entity": entity.name,
                "kind": "list",
            },
            {
                "name": f"New {entity.name}",
                "path": f"/{entity.plural}/new",
                "entity": entity.name,
                "kind": "form",
            },
            {
                "name": f"{entity.name} detail",
                "path": f"/{entity.plural}/{{row_id}}",
                "entity": entity.name,
                "kind": "detail",
            },
        ]
    return screens
