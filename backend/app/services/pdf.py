"""Quote PDFs: an HTML/CSS template rendered to PDF by WeasyPrint.

Two security measures, because the template contains text other people typed
(client names, area names):
- Jinja2 autoescaping: "<script>" in a client name is printed literally,
  never interpreted as HTML.
- A URL fetcher that allows NO protocols: even if markup did get in, the
  renderer can't read local files (file://) or reach internal network
  addresses (SSRF). The template needs nothing external: styles are inline
  and fonts are the system's.
"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.services.quote_documents import QuoteDocument

_templates = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(["html"]),
    # A typo'd variable name fails loudly instead of rendering as blank.
    undefined=StrictUndefined,
)


def format_cents(cents: int) -> str:
    """48300 -> "$483.00", with integer math only (no floats)."""
    dollars, remainder = divmod(cents, 100)
    return f"${dollars:,}.{remainder:02d}"


def format_decimal(value: Decimal) -> str:
    """Decimal("3.000") -> "3", Decimal("5.250") -> "5.25"."""
    return f"{value.normalize():f}"


def format_date(value: datetime | None, timezone: ZoneInfo) -> str:
    """UTC timestamp -> local calendar date, e.g. "September 25, 2026"."""
    return value.astimezone(timezone).strftime("%B %-d, %Y") if value else ""


_templates.filters.update(cents=format_cents, decimal=format_decimal)


def render_quote_html(
    document: QuoteDocument, *, generated_at: datetime, timezone: ZoneInfo
) -> str:
    return _templates.get_template("quote.html").render(
        doc=document,
        tax_percent=format_decimal(document.tax_rate * 100),
        generated_at=generated_at,
        date=lambda value: format_date(value, timezone),
    )


def render_quote_pdf(
    document: QuoteDocument, *, generated_at: datetime, timezone: ZoneInfo
) -> bytes:
    # Imported here, not at the top: WeasyPrint needs system libraries
    # (Pango), and a lazy import lets the rest of the API start and be tested
    # on machines without them. Only PDF requests need Pango.
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    html = render_quote_html(document, generated_at=generated_at, timezone=timezone)
    # allowed_protocols=(): an empty allow-list, so every URL is refused.
    pdf = HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=())).write_pdf()
    # WeasyPrint is untyped; check the type instead of trusting it blindly.
    if not isinstance(pdf, bytes):
        raise TypeError("WeasyPrint did not return PDF bytes")
    return pdf
