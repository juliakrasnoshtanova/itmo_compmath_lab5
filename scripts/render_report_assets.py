from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numerical
from datasets import sample_by_key
from interpolation import split_pairs

ASSETS = ROOT / "report_assets"
CURVE_POLY = "#b65436"
CURVE_EXACT = "#2e2923"
QUERY = "#a12828"
X1 = 1.051
X2 = 1.277


def render_computational_plot() -> None:
    sample = sample_by_key("variant4")
    x = list(sample.x)
    y = list(sample.y)

    grid = [1.0 + 0.7 * i / 400 for i in range(401)]
    poly = [numerical.lagrange(x, y, t) for t in grid]
    values = [numerical.lagrange(x, y, t) for t in (X1, X2)]

    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["font.size"] = 12
    figure, axes = plt.subplots(figsize=(8.0, 5.4), dpi=200)
    axes.plot(grid, poly, color=CURVE_POLY, linewidth=1.8, label=r"$P_6(x)$, интерполяционный многочлен")
    axes.plot(x, y, "o", color=CURVE_EXACT, markersize=5, label="Узлы интерполяции")
    axes.plot([X1, X2], values, "s", color=QUERY, markersize=6, label=r"Точки $X_1$ и $X_2$")
    for xx, value, name in ((X1, values[0], r"$X_1$"), (X2, values[1], r"$X_2$")):
        axes.axvline(xx, color=QUERY, linewidth=0.9, linestyle="--")
        axes.annotate(
            f"{name} = {xx}\n$P_6$ = {value:.5f}",
            (xx, value),
            textcoords="offset points",
            xytext=(12, -34),
            fontsize=10,
            color=QUERY,
        )

    axes.axhline(0.0, color="#8e8579", linewidth=0.9)
    axes.grid(True, color="#dcdcdc", linewidth=0.6)
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    axes.legend(loc="upper left", framealpha=1.0)
    figure.tight_layout()
    figure.savefig(ASSETS / "computational_plot.png")
    plt.close(figure)


def render_screenshots() -> None:
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QStyleFactory

    from app import Lab5QtApp

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setFont(QFont("Helvetica Neue", 12))
    window = Lab5QtApp()
    window.resize(1400, 1040)
    window.show()
    page = window.page

    def settle() -> None:
        for _ in range(8):
            app.processEvents()

    def shoot(name: str) -> None:
        settle()
        page.sidebar.scroll.verticalScrollBar().setValue(0)
        page.right_scroll.verticalScrollBar().setValue(0)
        settle()
        window.grab().save(str(ASSETS / name))

    settle()
    page.solve()
    shoot("screenshot_variant4.png")
    page.plot.grab().save(str(ASSETS / "plot_variant4.png"))
    host = page.right_scroll.widget()
    top = page.finite_card.geometry().top()
    bottom = page.divided_card.geometry().bottom()
    host.grab(QRect(0, top, host.width(), bottom - top + 1)).save(str(ASSETS / "tables_variant4.png"))

    page.sample_list.setCurrentRow(1)
    settle()
    page.solve()
    shoot("screenshot_function.png")

    page.expression_edit.setText("x*sin(x)")
    page.expression_edit.textEdited.emit(page.expression_edit.text())
    settle()
    page.function_timer.timeout.emit()
    settle()
    page.solve()
    shoot("screenshot_custom.png")

    page.sample_list.setCurrentRow(2)
    settle()
    page._fill_table(split_pairs((ROOT / "examples" / "lecture_divided.txt").read_text(encoding="utf-8")))
    page.query_edit.setText("0.22")
    settle()
    page.solve()
    shoot("screenshot_divided.png")

    page._fill_table([("1", "2"), ("2", "3"), ("2", "5"), ("3", "4")])
    settle()
    page.solve()
    shoot("screenshot_invalid.png")


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    render_computational_plot()
    render_screenshots()
    print("готово:", sorted(path.name for path in ASSETS.glob("*.png")))
