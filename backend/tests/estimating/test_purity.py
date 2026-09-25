"""Architecture rule 4, enforced: the estimating engine stays pure.

Reads the engine's source files (without importing them) and fails if any of
them imports something that would give it database, HTTP, or I/O access.
"""

import ast
from pathlib import Path

import app.estimating

ENGINE_DIR = Path(app.estimating.__file__).parent

# The engine may import only these top-level modules.
ALLOWED_IMPORTS = {"app", "dataclasses", "decimal", "enum", "uuid"}
# ...and within our own package, only the engine itself.
ALLOWED_APP_PREFIX = "app.estimating"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_engine_imports_only_the_standard_library_and_itself() -> None:
    files = sorted(ENGINE_DIR.glob("*.py"))
    assert files, "engine source files not found"

    violations = [
        f"{path.name}: imports {name}"
        for path in files
        for name in _imports(path)
        if name.split(".")[0] not in ALLOWED_IMPORTS
        or (name.split(".")[0] == "app" and not name.startswith(ALLOWED_APP_PREFIX))
    ]

    assert violations == [], "The estimating engine must stay pure:\n" + "\n".join(violations)
