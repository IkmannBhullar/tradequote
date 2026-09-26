"""Milestone 8: a second trade (flooring) works with seed data alone.

Architecture rule 5: trades are data. Flooring was added by adding a template
to the seed data; no application code changed. These tests prove the whole
product works for it, and guard against trade-specific code creeping in.
"""

import ast
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.config import get_settings
from tests.api_helpers import ApiUser

APPROVE = {"name": "Jane Homeowner", "accept_terms": True}


def lines(quote: dict[str, Any]) -> list[tuple[str, str, str, int]]:
    return [
        (line["description"], line["quantity"], line["unit"], line["total_cents"])
        for line in quote["line_items"]
    ]


def flooring_quote(owner: ApiUser) -> dict[str, Any]:
    """The hand-calculated example from the Milestone 8 plan."""
    quote_id = owner.create_quote()["id"]
    item = owner.template_item_id
    owner.add_area(
        quote_id, template_item_id=item("Laminate plank"), name="Living room", quantity="250"
    )
    owner.add_area(
        quote_id, template_item_id=item("Underlayment"), name="Living room", quantity="250"
    )
    owner.add_area(quote_id, template_item_id=item("Baseboard"), name="Living room", quantity="64")
    return owner.add_area(
        quote_id, template_item_id=item("Transition strips"), name="Doorways", quantity="2"
    )


# ---------------------------------------------------------------------------
# The math, end to end over the API
# ---------------------------------------------------------------------------


def test_flooring_quote_matches_the_hand_calculation(owner: ApiUser) -> None:
    quote = flooring_quote(owner)

    assert lines(quote) == [
        # 250 x 1.10 / 20 = 13.75 -> 14 boxes x $55
        ("Living room: Laminate flooring", "14.000", "box", 77_000),
        # 250 x 0.04 = 10.00 h x $65
        ("Living room: labor", "10.000", "hour", 65_000),
        # 250 x 1.05 / 100 = 2.625 -> 3 rolls x $35
        ("Living room: Foam underlayment", "3.000", "roll", 10_500),
        # 250 x 0.005 = 1.25 h x $65 = $81.25
        ("Living room: labor", "1.250", "hour", 8_125),
        # 64 x 1.10 / 8 = 8.8 -> 9 pieces x $12
        ("Living room: MDF baseboard (8 ft)", "9.000", "piece", 10_800),
        # 64 x 0.05 = 3.2 -> nearest quarter 3.25 h x $65 = $211.25
        ("Living room: labor", "3.250", "hour", 21_125),
        # 2 doorways / 1 per strip = 2 pieces x $25
        ("Doorways: Transition strip", "2.000", "piece", 5_000),
        # 2 x 0.5 = 1.00 h x $65
        ("Doorways: labor", "1.000", "hour", 6_500),
    ]
    # $2,040.50 + 5% tax (102.025 -> 102.03, half-up) = $2,142.53
    assert (quote["subtotal_cents"], quote["tax_cents"], quote["total_cents"]) == (
        204_050,
        10_203,
        214_253,
    )
    # No "coats" in flooring: every area uses the template's default of 1.
    assert {area["coats"] for area in quote["areas"]} == {1}
    assert [area["measure_type"] for area in quote["areas"]] == ["area", "area", "linear", "count"]


def test_one_quote_can_mix_trades(owner: ApiUser) -> None:
    quote_id = owner.create_quote()["id"]
    owner.add_area(quote_id)  # painting: 420 sq ft of walls = $460.00 before tax
    quote = owner.add_area(
        quote_id,
        template_item_id=owner.template_item_id("Laminate plank"),
        name="Kitchen",
        quantity="250",
    )  # flooring: $770.00 + $650.00 = $1,420.00 before tax

    assert (quote["subtotal_cents"], quote["tax_cents"], quote["total_cents"]) == (
        188_000,
        9_400,
        197_400,
    )


# ---------------------------------------------------------------------------
# The whole product loop, for flooring
# ---------------------------------------------------------------------------


def test_flooring_job_goes_from_quote_to_paid(owner: ApiUser, client: TestClient) -> None:
    quote = flooring_quote(owner)
    token = owner.ok("post", f"/quotes/{quote['id']}/send")["link"]["token"]
    approved = client.post("/public/quote/approve", headers={"X-Quote-Token": token}, json=APPROVE)
    assert approved.status_code == 200

    job_id = quote["job_id"]
    for status in ("scheduled", "in_progress", "completed"):
        owner.ok("patch", f"/jobs/{job_id}", json={"status": status})
    today = datetime.now(ZoneInfo(get_settings().display_timezone)).date().isoformat()
    paid = owner.ok(
        "post",
        f"/jobs/{job_id}/payments",
        201,
        json={"amount_cents": 214_253, "kind": "final", "received_on": today},
    )

    assert (paid["job_status"], paid["summary"]["balance_cents"]) == ("paid", 0)


@pytest.mark.pdf
def test_flooring_pdf(owner: ApiUser) -> None:
    quote = flooring_quote(owner)
    response = owner.get(f"/quotes/{quote['id']}/pdf")

    text = "".join(
        "".join(page.extract_text().split())
        for page in PdfReader(io.BytesIO(response.content)).pages
    )
    for expected in ("Laminate flooring", "14", "box", "Transition strip", "$2,142.53"):
        assert "".join(expected.split()) in text


# ---------------------------------------------------------------------------
# Guard: no trade-specific logic in application code
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parents[1] / "app"
# Seed data is the one place trades are allowed to be named.
ALLOWED = {APP_DIR / "seed.py"}
TRADE_WORD = re.compile(r"paint|floor(?!\()|drywall", re.IGNORECASE)


def _docstrings(tree: ast.Module) -> set[int]:
    """ids of docstring nodes: explaining with examples is fine; logic isn't."""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _code_words(path: Path) -> list[tuple[int, str]]:
    """String literals and identifiers (not comments or docstrings) in a file."""
    tree = ast.parse(path.read_text())
    skip = _docstrings(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            found.append((node.lineno, node.value))
        elif isinstance(node, ast.Name):
            found.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            found.append((node.lineno, node.attr))
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            found.append((node.lineno, node.name))
    return found


def test_application_code_never_names_a_trade() -> None:
    files = [path for path in APP_DIR.rglob("*.py") if path not in ALLOWED]
    assert len(files) > 30, "app sources not found"

    violations = [
        f"{path.relative_to(APP_DIR)}:{line}: {text!r}"
        for path in files
        for line, text in _code_words(path)
        if TRADE_WORD.search(text)
    ]

    assert violations == [], (
        "Trade-specific logic found (rule 5: trades are data, not code):\n" + "\n".join(violations)
    )
