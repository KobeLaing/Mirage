"""NFR-1 / SR-9: keep the layering honest.

- Routes (app/api) never import SQLAlchemy query building or repositories.
- Services can use a Session and catch DB exceptions, but can't build queries.
- No string-built SQL anywhere: no text()/exec_driver_sql, and nothing passes a
  string, f-string or concatenation to .execute().
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
# The one dialect hook (PRAGMA foreign_keys) is a fixed constant on a raw DB-API cursor.
RAW_SQL_ALLOWED = {APP / "db" / "session.py"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_routes_do_not_touch_the_database_layer():
    for path in (APP / "api").rglob("*.py"):
        for name in _imports(path):
            assert name in ("sqlalchemy.orm",) or not name.startswith("sqlalchemy"), (path, name)
            assert not name.startswith("app.repositories"), (path, name)
            assert not name.startswith("app.db.session"), (path, name)


def test_services_do_not_build_queries():
    for path in (APP / "services").rglob("*.py"):
        for name in _imports(path):
            assert name in ("sqlalchemy.orm", "sqlalchemy.exc") or not name.startswith("sqlalchemy"), (path, name)


def test_no_string_built_sql():
    for path in APP.rglob("*.py"):
        if path in RAW_SQL_ALLOWED:
            continue
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            assert name not in ("text", "exec_driver_sql", "literal_column"), f"{name}() in {path}"
            if name in ("execute", "scalar", "scalars") and node.args:
                first = node.args[0]
                assert not isinstance(first, (ast.Constant, ast.JoinedStr, ast.BinOp)), f"raw SQL in {path}"
