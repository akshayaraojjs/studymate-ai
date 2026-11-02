"""Turn the LaTeX fragments models emit into plain, readable text.

The chat renders markdown, not LaTeX, so a calculator answer written as
``(20 + 50) \\times 60 - \\frac{40}{8} = 4{,}195`` reaches the learner verbatim. This module
is a presentation cleanup, not a math renderer: it only handles the small set of markers
models use when restating arithmetic.
"""
from __future__ import annotations

import re

_FRACTION_RE = re.compile(r"\\[dt]?frac\s*\{\s*([^{}]*?)\s*\}\s*\{\s*([^{}]*?)\s*\}")
_SQRT_RE = re.compile(r"\\sqrt\s*\{\s*([^{}]*?)\s*\}")
_WRAPPER_RE = re.compile(r"\\(?:text|mathrm|operatorname|mathbf|mathit)\s*\{([^{}]*)\}")
_DELIMITER_RE = re.compile(r"\\[()\[\]]")
_SIZER_RE = re.compile(r"\\(?:left|right|bigl|bigr|Bigl|Bigr|biggl|biggr)\s*")
_THIN_THOUSANDS_RE = re.compile(r"(?<=\d)\\,(?=\d)")
_SPACING_RE = re.compile(r"\\[,;:!]")
_FUNCTION_RE = re.compile(
    r"\\(log10|log|ln|exp|sin|cos|tan|min|max|abs|round|ceil|floor)\b"
)

_SYMBOLS = {
    "times": "×",
    "div": "÷",
    "cdot": "·",
    "pm": "±",
    "mp": "∓",
    "approx": "≈",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "rightarrow": "→",
    "to": "→",
    "ldots": "…",
    "dots": "…",
}
_SYMBOL_RE = re.compile(
    r"\\(" + "|".join(sorted(_SYMBOLS, key=len, reverse=True)) + r")(?![A-Za-z])"
)


def normalize_math_markup(text: str) -> str:
    """Rewrite simple LaTeX math into the Unicode/plain equivalents markdown can show."""
    if not text or "\\" not in text and "{,}" not in text:
        return text

    cleaned = _FRACTION_RE.sub(lambda m: f"{m.group(1)}/{m.group(2)}", text)
    cleaned = _SQRT_RE.sub(lambda m: f"√({m.group(1)})", cleaned)
    cleaned = _WRAPPER_RE.sub(lambda m: m.group(1), cleaned)
    cleaned = _DELIMITER_RE.sub("", cleaned)
    cleaned = _SIZER_RE.sub("", cleaned)
    cleaned = _THIN_THOUSANDS_RE.sub(",", cleaned)
    cleaned = _SPACING_RE.sub("", cleaned)
    cleaned = cleaned.replace("\\ ", " ")
    cleaned = _SYMBOL_RE.sub(lambda m: _SYMBOLS[m.group(1)], cleaned)
    cleaned = _FUNCTION_RE.sub(lambda m: m.group(1), cleaned)

    # LaTeX thousand separators: 4{,}195 -> 4,195 (and a bare {} -> nothing).
    cleaned = cleaned.replace("{,}", ",").replace("{}", "")
    cleaned = cleaned.replace("\\%", "%").replace("\\$", "$")
    cleaned = cleaned.replace("\\_", "_").replace("\\&", "&")
    return cleaned
