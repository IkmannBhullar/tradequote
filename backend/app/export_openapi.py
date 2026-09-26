"""Print the API's OpenAPI schema as JSON (used to generate frontend types).

    uv run python -m app.export_openapi > ../frontend/openapi.json

Sorted keys and fixed indentation make the output stable, so CI can detect a
stale committed copy with a plain `git diff`.
"""

import json

from app.main import create_app

if __name__ == "__main__":
    print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))
