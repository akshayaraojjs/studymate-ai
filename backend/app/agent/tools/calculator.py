"""calculate tool: allowlisted arithmetic evaluation, never eval()."""
from __future__ import annotations

import ast
import math
from typing import Any

from app.agent.tools.base import AgentTool, ToolContext, ToolResult

MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 512
MAX_ABS_VALUE = 1e15

_ALLOWED_FUNCTIONS = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "ceil": math.ceil,
    "floor": math.floor,
}
_ALLOWED_CONSTANTS = {"pi": math.pi, "e": math.e}
_ALLOWED_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: None,  # handled with exponent limits
}
_ALLOWED_UNARY = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}


class CalculatorError(ValueError):
    pass


def safe_evaluate(expression: str) -> float:
    expression = expression.strip()
    if not expression:
        raise CalculatorError("Empty expression.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculatorError("Expression is too long.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError("Expression is not valid arithmetic.") from exc

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise CalculatorError("Only numbers are allowed.")
            return float(node.value)
        if isinstance(node, ast.BinOp):
            operator = _ALLOWED_BINARY.get(type(node.op))
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_EXPONENT:
                    raise CalculatorError("Exponent is too large.")
                if abs(left) > 1e6 and right > 10:
                    raise CalculatorError("Result would be too large.")
                result = left**right
            elif operator is None:
                raise CalculatorError("Operator is not allowed.")
            else:
                result = operator(left, right)
            return _check(result)
        if isinstance(node, ast.UnaryOp):
            operator = _ALLOWED_UNARY.get(type(node.op))
            if operator is None:
                raise CalculatorError("Unary operator is not allowed.")
            return _check(operator(evaluate(node.operand)))
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_CONSTANTS:
                return float(_ALLOWED_CONSTANTS[node.id])
            raise CalculatorError(f"Unknown identifier '{node.id}'.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
                raise CalculatorError("Function is not allowed.")
            if node.keywords:
                raise CalculatorError("Keyword arguments are not allowed.")
            arguments = [evaluate(arg) for arg in node.args]
            if node.func.id == "round" and len(arguments) == 2:
                # round() needs an integer number of digits, but the parser yields floats.
                if not arguments[1].is_integer():
                    raise CalculatorError("round() needs a whole number of digits.")
                arguments[1] = int(arguments[1])
            try:
                value = float(_ALLOWED_FUNCTIONS[node.func.id](*arguments))
            except (TypeError, ValueError, OverflowError) as exc:
                raise CalculatorError("Invalid arguments for that function.") from exc
            return _check(value)
        raise CalculatorError("Unsupported expression element.")

    try:
        result = evaluate(tree)
    except (ZeroDivisionError, OverflowError) as exc:
        raise CalculatorError("Arithmetic result is out of range or divides by zero.") from exc
    if not math.isfinite(result):
        raise CalculatorError("Result is not a finite number.")
    return result


def _check(value: float) -> float:
    if isinstance(value, complex):
        raise CalculatorError("Complex results are not supported.")
    if not math.isfinite(value):
        raise CalculatorError("Result is not a finite number.")
    if abs(value) > MAX_ABS_VALUE:
        raise CalculatorError("Result is too large.")
    return float(value)


def format_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"


async def calculate(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    expression = str(args.get("expression") or "").strip()
    if not expression:
        return ToolResult(content="Error: 'expression' is required.", ok=False, summary="Calculation failed")
    try:
        value = safe_evaluate(expression)
    except CalculatorError as exc:
        return ToolResult(
            content=f"Calculator error: {exc} Use only numbers, + - * / // % **, parentheses and basic functions.",
            ok=False,
            summary="Calculation failed",
        )
    except (ZeroDivisionError, OverflowError):
        return ToolResult(content="Calculator error: division by zero.", ok=False, summary="Calculation failed")

    formatted = format_number(value)
    ctx.calculations.append({"expression": expression, "result": formatted})
    return ToolResult(
        content=f"{expression} = {formatted}",
        ok=True,
        summary=f"Calculated {formatted}",
    )


calculate_tool = AgentTool(
    name="calculate",
    description=(
        "Evaluate an arithmetic expression safely. Use for percentages, accuracy, averages, "
        "unit conversions expressed as arithmetic, and similar numeric work. "
        "Supports numbers, + - * / // % **, parentheses and sqrt/log/log10/exp/sin/cos/tan/"
        "abs/round/min/max/ceil/floor, plus pi and e."
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression, e.g. '(85 / 100) * 100'.",
            }
        },
        "required": ["expression"],
    },
    handler=calculate,
    activity="Running the calculation",
)
