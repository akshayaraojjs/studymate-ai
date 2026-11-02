"""Answer text cleanup: LaTeX fragments become plain text."""
from __future__ import annotations

from app.services.text_format import normalize_math_markup


def test_normalises_calculator_style_latex():
    raw = "\\((20 + 50) \\times 60 - \\frac{40}{8} = 4{,}195\\)"
    assert normalize_math_markup(raw) == "(20 + 50) × 60 - 40/8 = 4,195"


def test_normalises_dividers_symbols_and_thin_spaces():
    raw = "\\frac{85}{100} \\cdot 100 = 85\\% and \\text{total} = 12\\,500"
    assert normalize_math_markup(raw) == "85/100 · 100 = 85% and total = 12,500"


def test_plain_text_is_returned_unchanged():
    text = "A database stores structured data in tables [1]."
    assert normalize_math_markup(text) == text
