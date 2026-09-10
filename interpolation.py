from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Callable

import numerical
from methods import MethodSpec


MIN_POINTS = 2
MAX_POINTS = 12
UNIFORM_TOLERANCE = 1e-8


@dataclass(frozen=True)
class PointSet:
    x: tuple[float, ...]
    y: tuple[float, ...]

    @property
    def count(self) -> int:
        return len(self.x)


@dataclass(frozen=True)
class InterpResult:
    method: MethodSpec
    value: float
    branch: str
    parameter: float | None


@dataclass(frozen=True)
class InterpFailure:
    method: MethodSpec
    reason: str


def ensure_finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"Значение \"{name}\" выходит за допустимый диапазон.")


def parse_float_token(text: str, label: str) -> float:
    trimmed = "" if text is None else text.strip()
    if not trimmed:
        raise ValueError(f"Не заполнено поле \"{label}\".")
    normalized = trimmed.replace(",", ".")
    try:
        value = float(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Некорректное число в поле \"{label}\": {trimmed}. Используйте число с точкой или запятой."
        ) from exc
    ensure_finite(value, label)
    return value


def parse_int_token(text: str, label: str) -> int:
    trimmed = "" if text is None else text.strip()
    if not trimmed:
        raise ValueError(f"Не заполнено поле \"{label}\".")
    try:
        return int(trimmed)
    except ValueError as exc:
        raise ValueError(f"Некорректное целое число в поле \"{label}\": {trimmed}.") from exc


def format_number(value: float) -> str:
    if not math.isfinite(value):
        return "-"
    if value == 0.0:
        return "0"
    return format(Decimal(str(value)).normalize(), "f")


def format_fixed(value: float, digits: int = 4) -> str:
    if not math.isfinite(value):
        return "-"
    if value != 0.0 and (abs(value) >= 1e6 or abs(value) < 1e-4):
        return f"{value:.{digits}e}"
    return f"{value:.{digits}f}"


def make_points(xs: list[float], ys: list[float]) -> PointSet:
    pairs = sorted(zip(xs, ys), key=lambda pair: pair[0])
    return PointSet(tuple(pair[0] for pair in pairs), tuple(pair[1] for pair in pairs))


def _validate(points: PointSet) -> None:
    if points.count < MIN_POINTS:
        raise ValueError(f"Нужно не меньше {MIN_POINTS} узлов, введено {points.count}.")
    if points.count > MAX_POINTS:
        raise ValueError(f"Слишком много узлов: {points.count}, допустимо не больше {MAX_POINTS}.")
    for i in range(1, points.count):
        if points.x[i] == points.x[i - 1]:
            raise ValueError(f"Узлы интерполяции должны быть различны: x = {format_number(points.x[i])} повторяется.")


def read_points(rows: list[tuple[int, str, str]]) -> PointSet:
    xs: list[float] = []
    ys: list[float] = []
    for number, x_text, y_text in rows:
        if not x_text.strip() and not y_text.strip():
            continue
        xs.append(parse_float_token(x_text, f"x в строке {number}"))
        ys.append(parse_float_token(y_text, f"y в строке {number}"))
    return make_points(xs, ys)


def parse_rows(rows: list[tuple[int, str, str]]) -> PointSet:
    points = read_points(rows)
    _validate(points)
    return points


def split_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.replace(";", " ").replace("\t", " ").strip()
        if not line:
            continue
        tokens = line.split()
        if len(tokens) != 2:
            raise ValueError(f"Строка {number}: ожидаются два числа «x y», получено {len(tokens)}.")
        pairs.append((tokens[0], tokens[1]))
    if not pairs:
        raise ValueError("В файле нет ни одного узла. Добавьте точки в соответствии с заданным форматом.")
    return pairs


def tabulate(fn: Callable[[float], float], left: float, right: float, count: int) -> PointSet:
    if count < MIN_POINTS:
        raise ValueError(f"Число узлов должно быть не меньше {MIN_POINTS}, задано {count}.")
    if count > MAX_POINTS:
        raise ValueError(f"Число узлов должно быть не больше {MAX_POINTS}, задано {count}.")
    if not left < right:
        raise ValueError("Левая граница отрезка должна быть меньше правой.")
    xs: list[float] = []
    ys: list[float] = []
    for i in range(count):
        x = right if i == count - 1 else left + (right - left) * i / (count - 1)
        try:
            y = float(fn(x))
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ValueError(f"Функция не определена в точке x = {format_number(x)}.") from exc
        ensure_finite(y, f"f({format_number(x)})")
        xs.append(x)
        ys.append(y)
    return make_points(xs, ys)


def step(points: PointSet) -> float:
    return points.x[1] - points.x[0]


def is_uniform(points: PointSet) -> bool:
    if points.count < 2:
        return False
    h = step(points)
    if h <= 0.0:
        return False
    tolerance = UNIFORM_TOLERANCE * max(1.0, abs(h))
    for i in range(1, points.count):
        if abs((points.x[i] - points.x[i - 1]) - h) > tolerance:
            return False
    return True


def is_inside(points: PointSet, xx: float) -> bool:
    return points.x[0] <= xx <= points.x[-1]


def position(points: PointSet, xx: float) -> str:
    if xx < points.x[0]:
        return f"левее x0 = {format_number(points.x[0])}, экстраполяция"
    if xx > points.x[-1]:
        return f"правее xn = {format_number(points.x[-1])}, экстраполяция"
    return f"внутри отрезка [{format_number(points.x[0])}; {format_number(points.x[-1])}]"


def finite_table(points: PointSet) -> list[list[float]] | None:
    if not is_uniform(points):
        return None
    return numerical.konech_raznosti(list(points.y))


def divided_table(points: PointSet) -> list[list[float]]:
    return numerical.razdel_raznosti(list(points.x), list(points.y))


def interpolate(points: PointSet, xx: float, method: MethodSpec) -> InterpResult | InterpFailure:
    if points.count < method.min_points:
        return InterpFailure(method, f"нужно не меньше {method.min_points} узлов")
    if method.uniform and not is_uniform(points):
        return InterpFailure(method, "узлы не равноотстоящие, конечные разности не применимы")

    x = list(points.x)
    y = list(points.y)
    try:
        value = float(method.evaluate(x, y, xx))
    except (ValueError, ZeroDivisionError, OverflowError):
        return InterpFailure(method, "не удалось вычислить значение")
    if not math.isfinite(value):
        return InterpFailure(method, "значение не определено")

    branch = "" if method.branch is None else method.branch(x, xx)
    parameter = None if method.parameter is None else method.parameter(x, xx)
    return InterpResult(method, value, branch, parameter)


def interpolate_all(points: PointSet, xx: float, methods: tuple[MethodSpec, ...]) -> list[InterpResult | InterpFailure]:
    if not methods:
        raise ValueError("Не выбран ни один метод интерполяции.")
    return [interpolate(points, xx, method) for method in methods]


def successful(results: list[InterpResult | InterpFailure]) -> list[InterpResult]:
    return [item for item in results if isinstance(item, InterpResult)]


def spread(results: list[InterpResult | InterpFailure]) -> float:
    values = [item.value for item in successful(results)]
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)
