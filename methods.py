from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numerical


EvaluateFn = Callable[[list[float], list[float], float], float]
BranchFn = Callable[[list[float], float], str]
ParameterFn = Callable[[list[float], float], float]


@dataclass(frozen=True)
class MethodSpec:
    key: str
    title: str
    formula: str
    evaluate: EvaluateFn
    min_points: int
    uniform: bool = False
    branch: BranchFn | None = None
    parameter: ParameterFn | None = None


def _newton_branch(x: list[float], xx: float) -> str:
    if numerical.vybor_newton(x, xx) == 1:
        return "первая формула, интерполирование вперёд"
    return "вторая формула, интерполирование назад"


def _newton_parameter(x: list[float], xx: float) -> float:
    h = x[1] - x[0]
    if numerical.vybor_newton(x, xx) == 1:
        return (xx - x[0]) / h
    return (xx - x[-1]) / h


METHODS: tuple[MethodSpec, ...] = (
    MethodSpec(
        key="lagrange",
        title="/•᷅‎‎•᷄\੭ Многочлен Лагранжа",
        formula="L(x) = Σ y_i · l_i(x)",
        evaluate=lambda x, y, xx: numerical.lagrange(x, y, xx),
        min_points=2,
    ),
    MethodSpec(
        key="newton_razdel",
        title="/•᷅‎‎•᷄\੭ Ньютон, разделённые разности",
        formula="N(x) = f(x0) + f(x0,x1)(x − x0) + …",
        evaluate=lambda x, y, xx: numerical.newton_razdel(x, y, xx),
        min_points=2,
        branch=_newton_branch,
    ),
    MethodSpec(
        key="newton_konech",
        title="/•᷅‎‎•᷄\੭ Ньютон, конечные разности",
        formula="N(x) = y0 + t·Δy0 + t(t−1)/2!·Δ²y0 + …",
        evaluate=lambda x, y, xx: numerical.newton_konech(x, y, xx),
        min_points=2,
        uniform=True,
        branch=_newton_branch,
        parameter=_newton_parameter,
    ),
)


def method_by_key(key: str) -> MethodSpec:
    for method in METHODS:
        if method.key == key:
            return method
    raise ValueError(f"Неизвестный метод: {key}.")
