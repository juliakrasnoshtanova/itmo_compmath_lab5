from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


CUSTOM_SAMPLE_KEY = "custom"
FUNCTION_SAMPLE_KEY = "function"
FUNCTION_KEY = "expression"
DEFAULT_EXPRESSION = "sin(x)"


@dataclass(frozen=True)
class PointSample:
    key: str
    title: str
    note: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    query: float

    def as_text(self) -> str:
        return "\n".join(f"{x} {y}" for x, y in zip(self.x, self.y))


@dataclass(frozen=True)
class FunctionSpec:
    key: str
    title: str
    formula: str
    fn: Callable[[float], float]


SAMPLES: tuple[PointSample, ...] = (
    PointSample(
        key="variant4",
        title="Вариант 4",
        note="таблица 1.4, 7 узлов, h = 0,1",
        x=(1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65),
        y=(0.1213, 1.1316, 2.1459, 3.1565, 4.1571, 5.1819, 6.1969),
        query=1.051,
    ),
)


FUNCTION_LEFT = 0.0
FUNCTION_RIGHT = 3.0
FUNCTION_COUNT = 7
FUNCTION_QUERY = 1.3


def sample_by_key(key: str) -> PointSample:
    for sample in SAMPLES:
        if sample.key == key:
            return sample
    raise ValueError(f"Неизвестный набор точек: {key}.")
