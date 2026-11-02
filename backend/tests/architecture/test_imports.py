"""Import-boundary rules that keep the read/write split honest.

- read_api never imports write_api (and vice versa): they talk only over HTTP.
- shared imports neither side.
- shared/engine does no I/O: no DB, HTTP or LLM imports.
- mock_supplier is an external system: it imports nothing from our sides.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _imports(package: str) -> list[tuple[Path, str]]:
    found = []
    for path in (ROOT / package).rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found += [(path, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.append((path, node.module))
    return found


def _violations(package: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{path.relative_to(ROOT)} imports {mod}"
        for path, mod in _imports(package)
        if any(mod == f or mod.startswith(f + ".") for f in forbidden)
    ]


def test_read_api_does_not_import_write_api():
    assert _violations("read_api", ("write_api", "mock_supplier")) == []


def test_write_api_does_not_import_read_api():
    assert _violations("write_api", ("read_api", "mock_supplier")) == []


def test_shared_imports_neither_side():
    assert _violations("shared", ("read_api", "write_api", "mock_supplier")) == []


def test_engine_has_no_io():
    forbidden = ("sqlmodel", "sqlalchemy", "sqlite3", "httpx", "requests", "openai", "fastapi", "shared.db")
    assert _violations("shared/engine", forbidden) == []


def test_mock_supplier_is_external():
    assert _violations("mock_supplier", ("read_api", "write_api")) == []
