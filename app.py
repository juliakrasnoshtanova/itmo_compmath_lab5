from __future__ import annotations

from contextlib import contextmanager
import math
from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from interpolation import (
    MAX_POINTS,
    MIN_POINTS,
    InterpFailure,
    InterpResult,
    PointSet,
    divided_table,
    finite_table,
    format_fixed,
    format_number,
    interpolate_all,
    is_inside,
    is_uniform,
    parse_float_token,
    parse_int_token,
    parse_rows,
    position,
    read_points,
    split_pairs,
    spread,
    step,
    successful,
    tabulate,
)
from datasets import (
    CUSTOM_SAMPLE_KEY,
    DEFAULT_EXPRESSION,
    FUNCTION_COUNT,
    FUNCTION_LEFT,
    FUNCTION_QUERY,
    FUNCTION_RIGHT,
    FUNCTION_SAMPLE_KEY,
    SAMPLES,
    FunctionSpec,
    sample_by_key,
)
from expression_parser import build_function_from_expression
from methods import METHODS
from plotting import PlotWidget, QueryMark, curve_color


APP_BG = "#f4efe4"
CARD_BG = "#fffaf0"
BORDER = "#d9cdbd"
TEXT = "#2e2923"
MUTED = "#665c52"
ACCENT = "#a5552d"
ACCENT_DARK = "#844220"
SUCCESS = "#1f6b43"
ERROR = "#a12828"
REQUIRED = "#a5442c"
OPTIONAL = "#2f7a52"

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _set_app_font(widget: QWidget, size: int, weight: int = QFont.Weight.Normal) -> None:
    font = QFont("SF Pro Display", size, weight)
    if font.family() == ".AppleSystemUIFont":
        font = QFont()
        font.setPointSize(size)
        font.setWeight(weight)
    widget.setFont(font)


class Card(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        _set_app_font(title_label, 13, QFont.Weight.DemiBold)
        layout.addWidget(title_label)


class Sidebar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SidebarHost")
        self.scroll = QScrollArea()
        self.scroll.setObjectName("SidebarScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def add_card(self, title: str) -> Card:
        card = Card(title)
        self.content_layout.insertWidget(self.content_layout.count() - 1, card)
        return card


class Lab5Page(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.file_report: str | None = None
        self._custom_pairs: list[tuple[str, str]] = []
        self._last_points: PointSet | None = None
        self._last_query: float | None = None
        self._last_results: list[InterpResult | InterpFailure] | None = None
        self._last_function: FunctionSpec | None = None
        self._check_changed = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.function_timer = QTimer(self)
        self.function_timer.setSingleShot(True)
        self.function_timer.setInterval(150)
        self.function_timer.timeout.connect(self._on_function_timer)
        self._build()
        self._populate()
        self.refresh_preview()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)
        layout.addWidget(splitter)

        self.sidebar = Sidebar()
        self.sidebar.setMinimumWidth(390)
        self.sidebar.setMaximumWidth(460)
        splitter.addWidget(self.sidebar)

        self.plot = PlotWidget()
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        right = QWidget()
        right.setObjectName("RightHost")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.plot, 0)

        self.finite_card = Card("⋆·˚ ༘ * Таблица конечных разностей")
        self.finite_hint = QLabel("Введите узлы, чтобы построить таблицу разностей.")
        self.finite_hint.setObjectName("HintLabel")
        self.finite_hint.setWordWrap(True)
        self.finite_card.layout().addWidget(self.finite_hint)
        self.finite_table = self._make_table()
        self.finite_card.layout().addWidget(self.finite_table)
        right_layout.addWidget(self.finite_card, 0)

        self.divided_card = Card("⋆·˚ ༘ * Таблица разделённых разностей")
        self.divided_hint = QLabel("Введите узлы, чтобы построить таблицу разностей.")
        self.divided_hint.setObjectName("HintLabel")
        self.divided_hint.setWordWrap(True)
        self.divided_card.layout().addWidget(self.divided_hint)
        self.divided_table = self._make_table()
        self.divided_card.layout().addWidget(self.divided_table)
        right_layout.addWidget(self.divided_card, 0)
        right_layout.addStretch(1)

        self.right_scroll = QScrollArea()
        self.right_scroll.setObjectName("RightScroll")
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.right_scroll.setWidget(right)
        self.plot.pointPicked.connect(self.add_picked_point)

        splitter.addWidget(self.right_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        data_card = self.sidebar.add_card("⋆ ˚｡⋆୨ Исходные данные ୧⋆ ˚｡⋆")
        data_layout = data_card.layout()

        sample_label = QLabel("Набор узлов ૮ ˶ᵔ ᵕ ᵔ˶ ა ⋆ˊˎ-")
        sample_label.setObjectName("HintLabel")
        data_layout.addWidget(sample_label)
        self.sample_list = QListWidget()
        self._configure_selector_list(self.sample_list)
        self.sample_list.currentRowChanged.connect(self._on_sample_changed)
        data_layout.addWidget(self.sample_list)

        points_label = QLabel("˚₊‧꒰აТаблица узлов໒꒱‧₊˚ вводите вручную или кликайте по графику")
        points_label.setObjectName("HintLabel")
        points_label.setWordWrap(True)
        data_layout.addWidget(points_label)

        self.points_table = QTableWidget(MAX_POINTS, 2)
        self.points_table.setHorizontalHeaderLabels(["x", "y"])
        self.points_table.setFont(QFont("Menlo", 11))
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.points_table.horizontalHeader().setHighlightSections(False)
        self.points_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.points_table.verticalHeader().setDefaultSectionSize(25)
        self.points_table.verticalHeader().setHighlightSections(False)
        for column, title in enumerate(("x", "y")):
            header_item = QTableWidgetItem(title)
            header_item.setForeground(QColor(MUTED))
            self.points_table.setHorizontalHeaderItem(column, header_item)
        for row in range(MAX_POINTS):
            number = QTableWidgetItem(str(row + 1))
            number.setForeground(QColor(REQUIRED if row < MIN_POINTS else OPTIONAL))
            self.points_table.setVerticalHeaderItem(row, number)
        self.points_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.points_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.points_table.itemChanged.connect(self._on_points_changed)
        data_layout.addWidget(self.points_table)

        self.rows_legend = QLabel(
            f"<span style='color:{REQUIRED}'>ʚଓ кол-во узлов: 1 - {MIN_POINTS} -- обязательно</span><br>"
            f"<span style='color:{OPTIONAL}'>ʚଓ {MIN_POINTS + 1} - {MAX_POINTS} -- по необходимости</span>"
        )
        self.rows_legend.setObjectName("HintLabel")
        self.rows_legend.setWordWrap(True)
        data_layout.addWidget(self.rows_legend)

        self.load_button = QPushButton("𓂃 Загрузить узлы из файла 𓂃")
        self.load_button.clicked.connect(self.load_points)
        data_layout.addWidget(self.load_button)

        self.file_format_label = QLabel("♡ Формат файла: каждый узел с новой строки, x и y через пробел или ;")
        self.file_format_label.setObjectName("HintLabel")
        self.file_format_label.setWordWrap(True)
        data_layout.addWidget(self.file_format_label)

        self.reset_button = QPushButton("୨୧ Сбросить узлы ୨୧ ")
        self.reset_button.clicked.connect(self.reset_points)
        data_layout.addWidget(self.reset_button)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setWordWrap(True)
        data_layout.addWidget(self.hint_label)

        function_card = self.sidebar.add_card("꒰ᐢ. .ᐢ꒱ Функция ꒰ᐢ. .ᐢ꒱")
        function_layout = function_card.layout()
        function_hint = QLabel(
            "Введите выражение f(x) через x ٩(ˊᗜˋ*)و например sin(x), cos(x), exp(-x^2) или x*sin(x), "
            "задайте отрезок [a; b] и число узлов n, таблица заполнится сама"
        )
        function_hint.setObjectName("HintLabel")
        function_hint.setWordWrap(True)
        function_layout.addWidget(function_hint)
        self.expression_edit = self._make_edit(DEFAULT_EXPRESSION)
        function_layout.addWidget(self.expression_edit)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(8)
        self.left_edit = self._make_edit(format_number(FUNCTION_LEFT))
        self.right_edit = self._make_edit(format_number(FUNCTION_RIGHT))
        self.count_edit = self._make_edit(str(FUNCTION_COUNT))
        for label_text, edit in (("a =", self.left_edit), ("b =", self.right_edit), ("n =", self.count_edit)):
            label = QLabel(label_text)
            label.setObjectName("HintLabel")
            interval_row.addWidget(label)
            interval_row.addWidget(edit, 1)
        function_layout.addLayout(interval_row)

        self.function_hint = QLabel()
        self.function_hint.setObjectName("HintLabel")
        self.function_hint.setWordWrap(True)
        function_layout.addWidget(self.function_hint)

        query_card = self.sidebar.add_card("✩°｡⋆ Точка интерполяции ⋆｡°✩")
        query_layout = query_card.layout()
        query_label = QLabel("Значение аргумента x ₍ᐢ. .ᐢ₎ в котором ищем значение функции")
        query_label.setObjectName("HintLabel")
        query_label.setWordWrap(True)
        query_layout.addWidget(query_label)
        self.query_edit = self._make_edit("")
        self.query_edit.textChanged.connect(self._update_query_hint)
        query_layout.addWidget(self.query_edit)
        self.query_hint = QLabel()
        self.query_hint.setObjectName("HintLabel")
        self.query_hint.setWordWrap(True)
        query_layout.addWidget(self.query_hint)

        methods_card = self.sidebar.add_card("✿ Методы интерполяции ✿")
        methods_layout = methods_card.layout()
        methods_hint = QLabel("Считаются все ✧ отметьте, какие показывать на графике")
        methods_hint.setObjectName("HintLabel")
        methods_hint.setWordWrap(True)
        methods_layout.addWidget(methods_hint)
        self.method_list = QListWidget()
        self._configure_selector_list(self.method_list)
        self.method_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        methods_layout.addWidget(self.method_list)

        actions_card = self.sidebar.add_card("𖥸 Действия 𖥸")
        actions_layout = actions_card.layout()
        self.solve_button = QPushButton("⟡ Вычислить ⟡")
        self.solve_button.setObjectName("PrimaryButton")
        self.solve_button.clicked.connect(self.solve)
        actions_layout.addWidget(self.solve_button)

        self.save_button = QPushButton("𝜗𝜚 Сохранить результат 𝜗𝜚")
        self.save_button.clicked.connect(self.save)
        actions_layout.addWidget(self.save_button)

        self.status_label = QLabel("Готово к работе.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        actions_layout.addWidget(self.status_label)

        result_card = self.sidebar.add_card("｡⭒⑅Результат⑅⭒｡")
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setMinimumHeight(340)
        _set_app_font(self.result_box, 11)
        self.result_box.setHtml(self._placeholder_html())
        result_card.layout().addWidget(self.result_box)

    def _populate(self) -> None:
        for sample in SAMPLES:
            item = QListWidgetItem(f"{sample.title}\n{sample.note}")
            item.setData(Qt.ItemDataRole.UserRole, sample.key)
            item.setSizeHint(QSize(0, 60))
            self.sample_list.addItem(item)
        function_item = QListWidgetItem("Функция\nтабулирование f(x) на отрезке [a; b]")
        function_item.setData(Qt.ItemDataRole.UserRole, FUNCTION_SAMPLE_KEY)
        function_item.setSizeHint(QSize(0, 60))
        self.sample_list.addItem(function_item)
        custom_item = QListWidgetItem("Свои узлы")
        custom_item.setData(Qt.ItemDataRole.UserRole, CUSTOM_SAMPLE_KEY)
        custom_item.setSizeHint(QSize(0, 44))
        self.sample_list.addItem(custom_item)

        for method in METHODS:
            item = QListWidgetItem(f"{method.title}\n{method.formula}")
            item.setData(Qt.ItemDataRole.UserRole, method.key)
            item.setSizeHint(QSize(0, 80))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.method_list.addItem(item)

        self._lock_selector_height(self.sample_list, self.sample_list.count())
        self._lock_selector_height(self.method_list, self.method_list.count())
        self.sample_list.setCurrentRow(0)
        self._update_reset_state()
        self.expression_edit.textEdited.connect(self._on_function_changed)
        self.left_edit.textChanged.connect(self._on_function_changed)
        self.right_edit.textChanged.connect(self._on_function_changed)
        self.count_edit.textChanged.connect(self._on_function_changed)
        self.method_list.itemChanged.connect(self._on_method_item_changed)
        self.method_list.itemClicked.connect(self._on_method_item_clicked)

    @staticmethod
    def _make_edit(text: str) -> QLineEdit:
        edit = QLineEdit(text)
        edit.setObjectName("FieldEdit")
        edit.setFont(QFont("Menlo", 11))
        return edit

    @staticmethod
    def _make_table() -> QTableWidget:
        table = QTableWidget(0, 0)
        table.setFont(QFont("Menlo", 11))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setDefaultSectionSize(25)
        table.verticalHeader().setHighlightSections(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return table

    def _checked_keys(self) -> set:
        keys = set()
        for row in range(self.method_list.count()):
            item = self.method_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                keys.add(str(item.data(Qt.ItemDataRole.UserRole)))
        return keys

    def _refresh_curves(self) -> None:
        if self._last_points is None or self._last_results is None or self._last_query is None:
            return
        keys = self._checked_keys()
        shown = [item for item in successful(self._last_results) if item.method.key in keys]
        computed = successful(self._last_results)
        value = computed[0].value if computed else math.nan
        function = None if self._last_function is None else self._last_function.fn
        self.plot.show_results(self._last_points, shown, QueryMark(self._last_query, value), function)

    def _on_method_item_changed(self, _item: QListWidgetItem) -> None:
        self._check_changed = True
        self._refresh_curves()

    def _on_method_item_clicked(self, item: QListWidgetItem) -> None:
        if not self._check_changed:
            state = Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
            item.setCheckState(state)
        self._check_changed = False

    def _selected_sample_key(self) -> str | None:
        item = self.sample_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def _is_custom_sample_selected(self) -> bool:
        return self._selected_sample_key() == CUSTOM_SAMPLE_KEY

    def _is_function_sample_selected(self) -> bool:
        return self._selected_sample_key() == FUNCTION_SAMPLE_KEY

    def _selected_function(self) -> FunctionSpec:
        return build_function_from_expression(self.expression_edit.text())

    def _current_function(self) -> FunctionSpec | None:
        if not self._is_function_sample_selected():
            return None
        try:
            return self._selected_function()
        except ValueError:
            return None

    def _on_sample_changed(self, row: int) -> None:
        if row < 0:
            return
        with self._frozen():
            self._switch_sample()

    def _switch_sample(self) -> None:
        self._update_reset_state()
        if self._is_custom_sample_selected():
            if any(x.strip() or y.strip() for x, y in self._custom_pairs):
                self._fill_table(self._custom_pairs)
            else:
                self.reset_points()
            return
        if self._is_function_sample_selected():
            self.query_edit.setText(format_number(FUNCTION_QUERY))
            self._regenerate_function()
            return
        sample = sample_by_key(str(self._selected_sample_key()))
        self.query_edit.setText(format_number(sample.query))
        self._fill_table([(str(x), str(y)) for x, y in zip(sample.x, sample.y)])

    def _on_function_changed(self, *_args) -> None:
        with self._frozen():
            self._select_function_sample()
        self.function_timer.start()

    def _on_function_timer(self) -> None:
        with self._frozen():
            self._regenerate_function()

    def _regenerate_function(self) -> None:
        try:
            function = self._selected_function()
            left = parse_float_token(self.left_edit.text(), "a")
            right = parse_float_token(self.right_edit.text(), "b")
            count = parse_int_token(self.count_edit.text(), "n")
            points = tabulate(function.fn, left, right, count)
        except ValueError as exc:
            self.function_hint.setText(str(exc))
            self._fill_table([])
            return
        self.function_hint.setText(f"{function.formula},  h = {format_fixed(step(points), 4)}")
        self._fill_table([(format_number(x), format_number(y)) for x, y in zip(points.x, points.y)])

    def _on_points_changed(self, _item: QTableWidgetItem | None = None) -> None:
        self._select_custom_sample()
        self._remember_custom()
        self._update_hint()
        self.preview_timer.start()

    def _update_tables(self, points: PointSet | None, error: str | None = None) -> None:
        if points is None:
            message = "Введите узлы, чтобы построить таблицу разностей." if error is None else error
            self._fill_difference_table(self.finite_table, self.finite_hint, None, [], message)
            self._fill_difference_table(self.divided_table, self.divided_hint, None, [], message)
            return
        finite = finite_table(points)
        if finite is None:
            self._fill_difference_table(
                self.finite_table, self.finite_hint, None, [],
                "Узлы не равноотстоящие, конечные разности не строятся.",
            )
        else:
            labels = ["x", "y"] + [f"Δ{self._power(k)}y" for k in range(1, points.count)]
            self._fill_difference_table(
                self.finite_table, self.finite_hint, (points, finite), labels,
                f"h = {format_number(step(points))},  Δᵏyi = Δᵏ⁻¹yi+1 − Δᵏ⁻¹yi",
            )
        divided = divided_table(points)
        labels = ["x", "y"] + [f"{k}-й пор." for k in range(1, points.count)]
        self._fill_difference_table(
            self.divided_table, self.divided_hint, (points, divided), labels,
            "f(xi, …, xi+k) = (f(xi+1, …, xi+k) − f(xi, …, xi+k−1)) / (xi+k − xi)",
        )

    @staticmethod
    def _power(k: int) -> str:
        return "" if k == 1 else str(k).translate(SUPERSCRIPT)

    def _fill_difference_table(
        self,
        table: QTableWidget,
        hint: QLabel,
        data: tuple[PointSet, list[list[float]]] | None,
        labels: list[str],
        message: str,
    ) -> None:
        hint.setText(message)
        table.clearContents()
        if data is None:
            table.setRowCount(0)
            table.setColumnCount(0)
        else:
            points, columns = data
            table.setColumnCount(len(labels))
            table.setHorizontalHeaderLabels(labels)
            table.setRowCount(points.count)
            for row in range(points.count):
                values = [points.x[row]] + [column[row] if row < len(column) else math.nan for column in columns]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem("" if not math.isfinite(value) else format_number(value))
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row, column, cell)
            table.resizeColumnsToContents()
        height = (
            table.horizontalHeader().sizeHint().height()
            + 25 * table.rowCount()
            + 2 * table.frameWidth()
            + table.horizontalScrollBar().sizeHint().height()
        )
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    def adjust_metrics(self) -> None:
        text = self.hint_label.text()
        self.hint_label.setText("A\nA")
        self.hint_label.setFixedHeight(self.hint_label.sizeHint().height())
        self.hint_label.setText(text)
        height = (
            self.points_table.horizontalHeader().sizeHint().height()
            + sum(self.points_table.rowHeight(row) for row in range(MAX_POINTS))
            + 2 * self.points_table.frameWidth()
        )
        self.points_table.setMinimumHeight(height)
        self.points_table.setMaximumHeight(height)

    def _table_rows(self) -> list[tuple[int, str, str]]:
        rows = []
        for row in range(self.points_table.rowCount()):
            x_item = self.points_table.item(row, 0)
            y_item = self.points_table.item(row, 1)
            rows.append((row + 1, "" if x_item is None else x_item.text(), "" if y_item is None else y_item.text()))
        return rows

    def _current_points(self) -> PointSet:
        return parse_rows(self._table_rows())

    def _remember_custom(self) -> None:
        if self._is_custom_sample_selected():
            self._custom_pairs = [(x, y) for _, x, y in self._table_rows()]

    def _fill_table(self, pairs: list[tuple[str, str]]) -> None:
        with self._frozen():
            self.file_report = None
            self._last_points = None
            self._last_query = None
            self._last_results = None
            self._last_function = None
            self.result_box.setHtml(self._placeholder_html())
            self.points_table.blockSignals(True)
            self.points_table.clearContents()
            for row in range(MAX_POINTS):
                x_text, y_text = pairs[row] if row < len(pairs) else ("", "")
                self.points_table.setItem(row, 0, QTableWidgetItem(x_text))
                self.points_table.setItem(row, 1, QTableWidgetItem(y_text))
            self.points_table.blockSignals(False)
            self._update_hint()
            self.refresh_preview()

    def _select_sample(self, key: str) -> None:
        if self._selected_sample_key() == key:
            return
        for row in range(self.sample_list.count()):
            if str(self.sample_list.item(row).data(Qt.ItemDataRole.UserRole)) == key:
                self.sample_list.blockSignals(True)
                self.sample_list.setCurrentRow(row)
                self.sample_list.blockSignals(False)
                break
        self._update_reset_state()

    def _select_custom_sample(self) -> None:
        self._select_sample(CUSTOM_SAMPLE_KEY)

    def _select_function_sample(self) -> None:
        self._select_sample(FUNCTION_SAMPLE_KEY)

    def _update_reset_state(self) -> None:
        self.reset_button.setEnabled(self._is_custom_sample_selected())

    @contextmanager
    def _frozen(self):
        if not self.updatesEnabled():
            yield
            return
        sidebar = self.sidebar.scroll.verticalScrollBar()
        right = self.right_scroll.verticalScrollBar()
        offsets = (sidebar.value(), right.value())
        self.setUpdatesEnabled(False)
        try:
            yield
        finally:
            sidebar.setValue(offsets[0])
            right.setValue(offsets[1])
            self.setUpdatesEnabled(True)

    def reset_points(self) -> None:
        self._custom_pairs = []
        self._fill_table([])
        self._set_status("︵ 𐔌 Таблица очищена ꪆ⏜ׅ ✶ вводите узлы вручную или кликайте по графику.", success=True)

    def _update_hint(self) -> None:
        try:
            points = self._current_points()
        except ValueError as exc:
            self.hint_label.setText(str(exc))
            return
        grid = f"равноотстоящие, h = {format_fixed(step(points), 3)}" if is_uniform(points) else "неравноотстоящие"
        self.hint_label.setText(
            f"Узлов: {points.count}, {grid}\n"
            f"x ∈ [{format_fixed(min(points.x), 3)}; {format_fixed(max(points.x), 3)}]   "
            f"y ∈ [{format_fixed(min(points.y), 3)}; {format_fixed(max(points.y), 3)}]"
        )

    def _update_query_hint(self, *_args) -> None:
        try:
            xx = parse_float_token(self.query_edit.text(), "x")
        except ValueError as exc:
            self.query_hint.setStyleSheet("")
            self.query_hint.setText(str(exc))
            return
        try:
            points = self._current_points()
        except ValueError:
            self.query_hint.setStyleSheet("")
            self.query_hint.setText(f"x = {format_number(xx)}")
            return
        inside = is_inside(points, xx)
        self.query_hint.setStyleSheet("" if inside else f"color: {ACCENT};")
        self.query_hint.setText(f"x = {format_number(xx)}, {position(points, xx)}")

    def refresh_preview(self) -> None:
        try:
            points = read_points(self._table_rows())
        except ValueError as exc:
            self.plot.show_message(str(exc))
            self._update_tables(None, str(exc))
            self._update_query_hint()
            return
        function = self._current_function()
        self.plot.show_points(points, None if function is None else function.fn)
        try:
            self._update_tables(self._current_points())
        except ValueError as exc:
            self._update_tables(None, str(exc))
        self._update_query_hint()

    def add_picked_point(self, x: float, y: float) -> None:
        row = self._first_free_row()
        if row is None:
            self._set_status(f"Таблица заполнена: {MAX_POINTS} из {MAX_POINTS} узлов.", success=False)
            return
        self.points_table.blockSignals(True)
        self.points_table.item(row, 0).setText(f"{x:.3f}")
        self.points_table.item(row, 1).setText(f"{y:.3f}")
        self.points_table.blockSignals(False)
        self.points_table.setCurrentCell(row, 0)
        self._select_custom_sample()
        self._remember_custom()
        self._update_hint()
        self.refresh_preview()
        self._set_status(f"Узел ({x:.3f}; {y:.3f}) добавлен в строку {row + 1}.", success=True)

    def _first_free_row(self) -> int | None:
        for row in range(MAX_POINTS):
            x_item = self.points_table.item(row, 0)
            y_item = self.points_table.item(row, 1)
            x_text = "" if x_item is None else x_item.text().strip()
            y_text = "" if y_item is None else y_item.text().strip()
            if not x_text and not y_text:
                return row
        return None

    def solve(self) -> None:
        try:
            points = self._current_points()
            xx = parse_float_token(self.query_edit.text(), "x")
            results = interpolate_all(points, xx, METHODS)
            function = self._current_function()
            exact = self._exact_value(function, xx)
            self._last_points = points
            self._last_query = xx
            self._last_results = results
            self._last_function = function
            self.result_box.setHtml(self._format_report(points, xx, results, exact))
            report = self.result_box.toPlainText().strip()
            self.file_report = report + "\n" + self._tables_text(points)
            self._refresh_curves()
            computed = successful(results)
            if not computed:
                self._set_status("Ни один метод не применим к этим данным.", success=False)
            else:
                self._set_status(
                    f"(๑˃ᴗ˂)ﻭ Значение в точке x = {format_number(xx)} найдено {len(computed)} из {len(results)} методами.",
                    success=True,
                )
        except Exception as exc:
            self.file_report = None
            self._last_points = None
            self._last_query = None
            self._last_results = None
            self._last_function = None
            self.result_box.setHtml(f"<div style='color:{ERROR}'>{exc}</div>")
            self._set_status(str(exc), success=False)

    @staticmethod
    def _exact_value(function: FunctionSpec | None, xx: float) -> float | None:
        if function is None:
            return None
        try:
            value = float(function.fn(xx))
        except (ValueError, OverflowError, ZeroDivisionError):
            return None
        return value if math.isfinite(value) else None

    def load_points(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузка таблицы узлов",
            str(Path.cwd()),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        try:
            pairs = split_pairs(Path(path).read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError:
            self._set_status("Файл не является текстовым файлом в кодировке UTF-8.", success=False)
            return
        except OSError as exc:
            self._set_status(f"Не удалось прочитать файл: {exc}", success=False)
            return
        except ValueError as exc:
            self._set_status(str(exc), success=False)
            return
        if len(pairs) > MAX_POINTS:
            self._set_status(f"В файле {len(pairs)} узлов, допустимо не больше {MAX_POINTS}.", success=False)
            return
        self._select_custom_sample()
        self._fill_table(pairs)
        self._remember_custom()
        self._set_status(f"Узлы загружены из файла «{Path(path).name}».", success=True)

    def save(self) -> None:
        if self.file_report is None:
            QMessageBox.information(self, "Нет данных", "Сначала получите решение, потом его можно сохранить.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранение результата",
            str(Path(__file__).resolve().parent / "result.txt"),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.file_report.strip() + "\n", encoding="utf-8")
        except OSError as exc:
            self._set_status(f"Не удалось сохранить файл: {exc}", success=False)
            return
        self._set_status(f"Результат сохранен в файл «{Path(path).name}».", success=True)

    @staticmethod
    def _placeholder_html() -> str:
        return f"<div style='color:{MUTED}'>Нажмите «Вычислить», чтобы найти значение функции в точке x ✧</div>"

    @staticmethod
    def _card_html(content: str, background: str) -> str:
        return (
            f"<table width='100%' cellpadding='7' cellspacing='0' "
            f"style='background-color:{background}; border:1px solid {BORDER}'>"
            f"<tr><td>{content}</td></tr></table>"
            f"<div style='font-size:3pt'>&nbsp;</div>"
        )

    @staticmethod
    def _value_html(label: str, text: str) -> str:
        return f"<br><span style='color:{MUTED}'>{label}</span> = <span style='color:{TEXT}'>{text}</span>"

    def _method_card_html(self, item: InterpResult | InterpFailure, xx: float, exact: float | None) -> str:
        if isinstance(item, InterpFailure):
            content = (
                f"<span style='color:{MUTED}; font-weight:bold'>{item.method.title}</span>"
                f"<br><span style='color:{MUTED}'>{item.method.formula}</span>"
                f"<br><span style='color:{ERROR}'>не вычислен: {item.reason}</span>"
            )
            return self._card_html(content, "#f7f2ea")

        content = (
            f"<span style='color:{curve_color(item.method)}; font-weight:bold'>{item.method.title}</span>"
            f"<br><span style='color:{MUTED}'>{item.method.formula}</span>"
        )
        if item.branch:
            note = item.branch
            if item.parameter is not None:
                note += f", t = {format_number(item.parameter)}"
            content += f"<br><span style='color:{MUTED}'>{note}</span>"
        content += (
            f"<br><span style='color:{MUTED}'>P({format_number(xx)})</span> = "
            f"<span style='color:{TEXT}; font-weight:bold'>{format_number(item.value)}</span>"
        )
        if exact is not None:
            content += self._value_html("|P − f|", format_fixed(abs(item.value - exact), 3))
        return self._card_html(content, CARD_BG)

    def _comparison_html(self, computed: list[InterpResult], exact: float | None) -> str:
        content = f"<span style='color:{ACCENT_DARK}; font-weight:bold'>Сравнение значений</span>"
        for item in computed:
            content += (
                f"<br><span style='color:{curve_color(item.method)}'>{item.method.title}</span>"
                f"<span style='color:{MUTED}'> — </span>{format_number(item.value)}"
            )
        content += self._value_html("разброс между методами", format_fixed(spread(computed), 3))
        if exact is not None:
            content += self._value_html("точное значение f(x)", format_number(exact))
        return self._card_html(content, "#f4e5d9")

    def _format_report(self, points: PointSet, xx: float, results: list[InterpResult | InterpFailure], exact: float | None) -> str:
        grid = f"равноотстоящие, h = {format_number(step(points))}" if is_uniform(points) else "неравноотстоящие"
        inside = is_inside(points, xx)
        parts = [
            f"<div style='color:{MUTED}'>Число узлов n: "
            f"<span style='color:{TEXT}; font-weight:bold'>{points.count}</span>"
            f"<br>Узлы: <span style='color:{TEXT}'>{grid}</span>"
            f"<br>Точка x = <span style='color:{TEXT}; font-weight:bold'>{format_number(xx)}</span>, "
            f"<span style='color:{TEXT if inside else ACCENT}'>{position(points, xx)}</span>"
            f"<br>Вычислено методов: "
            f"<span style='color:{TEXT}; font-weight:bold'>{len(successful(results))} из {len(results)}</span>"
            f"</div><div style='font-size:5pt'>&nbsp;</div>"
        ]
        for item in results:
            parts.append(self._method_card_html(item, xx, exact))

        computed = successful(results)
        if not computed:
            parts.append(f"<div style='color:{ERROR}'>Ни один метод не применим к этим данным.</div>")
            return "".join(parts)

        parts.append(self._comparison_html(computed, exact))
        return "".join(parts)

    def _tables_text(self, points: PointSet) -> str:
        lines = [""]
        finite = finite_table(points)
        if finite is None:
            lines.append("Таблица конечных разностей: узлы не равноотстоящие, не строится.")
        else:
            lines.append("Таблица конечных разностей:")
            labels = ["x", "y"] + [f"d{k}y" for k in range(1, points.count)]
            lines.extend(self._table_lines(points, finite, labels))
        lines.append("")
        lines.append("Таблица разделённых разностей:")
        labels = ["x", "y"] + [f"f{k}" for k in range(1, points.count)]
        lines.extend(self._table_lines(points, divided_table(points), labels))
        return "\n".join(lines)

    @staticmethod
    def _table_lines(points: PointSet, columns: list[list[float]], labels: list[str]) -> list[str]:
        rows = [tuple(labels)]
        for i in range(points.count):
            values = [format_number(points.x[i])]
            for column in columns:
                values.append(format_number(column[i]) if i < len(column) else "")
            rows.append(tuple(values))
        widths = [max(len(row[column]) for row in rows) + 2 for column in range(len(labels))]
        return ["   " + "".join(cell.rjust(width) for cell, width in zip(row, widths)) for row in rows]

    def _set_status(self, text: str, success: bool) -> None:
        color = SUCCESS if success else ERROR
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(text)

    @staticmethod
    def _configure_selector_list(widget: QListWidget) -> None:
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setUniformItemSizes(False)
        widget.setWrapping(False)
        widget.setWordWrap(True)
        widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @staticmethod
    def _lock_selector_height(widget: QListWidget, rows: int) -> None:
        height = widget.frameWidth() * 2 + 2
        for index in range(rows):
            row_height = widget.sizeHintForRow(index)
            item_hint = widget.item(index).sizeHint().height()
            height += max(row_height, item_hint, 36)
        widget.setMinimumHeight(height)
        widget.setMaximumHeight(height)


class Lab5QtApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ᓚᘏᗢ Лабораторная работа №5 ᗢᘏᓗ")
        self.resize(1180, 760)
        self.setMinimumSize(1060, 640)
        self.page = Lab5Page()
        self.setCentralWidget(self.page)
        self._apply_styles()
        self.page.adjust_metrics()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {APP_BG};
                color: {TEXT};
            }}
            #SidebarHost {{
                background: {APP_BG};
            }}
            #SidebarScroll {{
                background: {APP_BG};
                border: none;
            }}
            #Card {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            #CardTitle {{
                color: {TEXT};
            }}
            #HintLabel, #StatusLabel {{
                color: {MUTED};
            }}
            QListWidget, QLineEdit, QTextEdit {{
                background: #fffdfa;
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT};
                selection-background-color: #efd7c8;
                selection-color: {TEXT};
            }}
            QLineEdit#FieldEdit {{
                min-height: 26px;
                padding: 2px 8px;
            }}
            QTableWidget QLineEdit {{
                border: 1px solid {ACCENT};
                border-radius: 0;
                padding: 0 4px;
                margin: 0;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background: #efd7c8;
            }}
            QTableWidget {{
                background: #fffdfa;
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT};
                gridline-color: {BORDER};
                selection-background-color: #efd7c8;
                selection-color: {TEXT};
            }}
            QTableWidget::item {{
                padding: 2px 6px;
            }}
            QHeaderView {{
                background: #f4e5d9;
            }}
            QHeaderView::section {{
                background: #f4e5d9;
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 4px 6px;
            }}
            QTableCornerButton::section {{
                background: #f4e5d9;
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
            }}
            QListWidget::indicator {{
                width: 15px;
                height: 15px;
                margin-right: 6px;
                border: 1px solid {BORDER};
                border-radius: 4px;
                background: #fffdfa;
            }}
            QListWidget::indicator:hover {{
                border-color: {ACCENT};
            }}
            QListWidget::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT_DARK};
            }}
            QPushButton {{
                min-height: 34px;
                border: 1px solid {BORDER};
                border-radius: 6px;
                background: #fffdfa;
                color: {TEXT};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: #f4e5d9;
            }}
            QPushButton:disabled {{
                color: #b3a898;
                background: #faf6ef;
            }}
            QPushButton#PrimaryButton {{
                background: {ACCENT};
                color: white;
                border-color: {ACCENT_DARK};
                font-weight: 600;
            }}
            #RightHost, #RightScroll {{
                background: {APP_BG};
                border: none;
            }}
            QPushButton#PrimaryButton:hover {{
                background: {ACCENT_DARK};
            }}
            """
        )
