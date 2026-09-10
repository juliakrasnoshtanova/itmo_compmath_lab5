from __future__ import annotations

import math

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from datasets import FUNCTION_KEY, FunctionSpec


_X = sympy.Symbol("x")
_ALLOWED_NAMES = {
    "x": _X,
    "e": sympy.E,
    "pi": sympy.pi,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "tg": sympy.tan,
    "asin": sympy.asin,
    "arcsin": sympy.asin,
    "acos": sympy.acos,
    "arccos": sympy.acos,
    "atan": sympy.atan,
    "arctan": sympy.atan,
    "arctg": sympy.atan,
    "sqrt": sympy.sqrt,
    "abs": sympy.Abs,
    "ln": sympy.log,
    "log": sympy.log,
    "exp": sympy.exp,
}
_ALLOWED_FUNCTION_NAMES = {
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sqrt",
    "Abs",
    "log",
    "exp",
}
_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


def build_function_from_expression(expression: str, *, title: str = "Функция") -> FunctionSpec:
    source = (expression or "").strip().replace(",", ".")
    if not source:
        raise ValueError("Введите выражение f(x).")

    try:
        parsed = parse_expr(
            source,
            local_dict=_ALLOWED_NAMES,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise ValueError(f"Некорректное выражение: {exc}") from exc

    extra_symbols = sorted(str(symbol) for symbol in parsed.free_symbols if symbol != _X)
    if extra_symbols:
        joined = ", ".join(extra_symbols)
        raise ValueError(f"Разрешена только переменная x. Найдены посторонние символы: {joined}.")
    if _X not in parsed.free_symbols:
        raise ValueError("Выражение должно зависеть от x.")
    extra_functions = sorted(
        function.func.__name__
        for function in parsed.atoms(sympy.Function)
        if function.func.__name__ not in _ALLOWED_FUNCTION_NAMES
    )
    if extra_functions:
        joined = ", ".join(extra_functions)
        raise ValueError(f"Некорректное выражение: неподдерживаемая функция {joined}.")

    evaluator = sympy.lambdify(_X, parsed, modules=["math"])
    return FunctionSpec(
        key=FUNCTION_KEY,
        title=title,
        formula=f"f(x) = {source}",
        fn=_wrap_unary(evaluator, "f(x)"),
    )


def _wrap_unary(function, label: str):
    def wrapped(x: float) -> float:
        try:
            value = function(x)
        except Exception as exc:
            raise ValueError(f"Не удалось вычислить {label} при x = {x}: {exc}") from exc
        if not isinstance(value, (int, float)):
            value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"Получено неконечное значение {label} при x = {x}.")
        return float(value)

    return wrapped
