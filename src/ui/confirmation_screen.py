try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt, pyqtSignal
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt, pyqtSignal

from src.logic.calculator import OrderPlan

_DIRECTION_COLORS = {"LONG": "#2ea043", "SHORT": "#e5534b"}


def _fmt(value: float) -> str:
    """Format float removing trailing zeros (e.g. 84320.50000000 → 84320.5)."""
    return f"{value:.8f}".rstrip("0").rstrip(".")


class ConfirmationScreen(QtWidgets.QWidget):
    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, ui: dict = None, parent=None):
        super().__init__(parent)
        self._ui = ui or {}
        self._setup_ui()

    def _t(self, key, fallback=""):
        return self._ui.get(key, fallback)

    def _setup_ui(self):
        try:
            align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            align_center = Qt.AlignmentFlag.AlignCenter
        except AttributeError:
            align_right = Qt.AlignRight | Qt.AlignVCenter
            align_center = Qt.AlignCenter

        self._align_right = align_right

        title = QtWidgets.QLabel(self._t("confirm_title", "Подтвердить вход в позицию?"))
        title.setAlignment(align_center)
        f = title.font()
        f.setBold(True)
        title.setFont(f)

        self._form = QtWidgets.QFormLayout()
        self._form.setSpacing(6)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setLabelAlignment(align_right)

        self._yes_btn = QtWidgets.QPushButton(self._t("confirm_yes", "Да"))
        self._no_btn = QtWidgets.QPushButton(self._t("confirm_no", "Нет"))
        self._yes_btn.setMinimumWidth(100)
        self._no_btn.setMinimumWidth(100)
        self._yes_btn.clicked.connect(self.confirmed)
        self._no_btn.clicked.connect(self.cancelled)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._yes_btn)
        btn_row.addSpacing(16)
        btn_row.addWidget(self._no_btn)
        btn_row.addStretch()

        form_wrapper = QtWidgets.QVBoxLayout()
        form_wrapper.addStretch()
        form_wrapper.addLayout(self._form)
        form_wrapper.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addLayout(form_wrapper, stretch=1)
        layout.addLayout(btn_row)

    def set_plan(self, plan: OrderPlan) -> None:
        """Populate the table with values from plan."""
        while self._form.rowCount() > 0:
            self._form.removeRow(0)

        def row(label: str, value: str, bold: bool = False):
            lbl = QtWidgets.QLabel(value)
            if bold:
                f = lbl.font()
                f.setBold(True)
                lbl.setFont(f)
            self._form.addRow(label, lbl)

        # Direction with color
        dir_lbl = QtWidgets.QLabel(plan.direction)
        dir_lbl.setStyleSheet(
            f"color: {_DIRECTION_COLORS.get(plan.direction, '')}; font-weight: bold;"
        )
        self._form.addRow(self._t("confirm_direction", "Направление"), dir_lbl)

        row(self._t("confirm_margin_type", "Тип маржи"), plan.margin_type)
        row(self._t("confirm_ticker", "Тикер"), plan.symbol)
        pos_str = f"{_fmt(plan.position_size)} USDT"
        if plan.position_size_rounded:
            pos_str += f"  ({self._t('confirm_rounded', 'округлено')})"
        row(self._t("confirm_position", "Позиция"), pos_str)
        row(self._t("confirm_leverage", "Плечо"), f"{plan.leverage:.0f}x")
        row(self._t("confirm_margin", "Маржа"), f"{plan.margin:.2f} USDT")

        if plan.is_market:
            entry_str = f"{self._t('confirm_entry_market', 'по рынку')} ({_fmt(plan.entry_price)})"
        else:
            entry_str = _fmt(plan.entry_price)
        row(self._t("confirm_entry_price", "Цена входа"), entry_str)

        row(self._t("confirm_sl", "Стоп-лосс"), f"{_fmt(plan.sl_price)}  ({plan.stop_loss_pct}%)")
        row(self._t("confirm_final_tp", "Финальный TP"), f"{_fmt(plan.final_tp_price)}  ({plan.final_tp_pct}%)")

        if plan.is_market:
            row(self._t("confirm_tp1", "TP1"), f"{_fmt(plan.tp1_price)}  ({plan.tp1_offset_pct}%,  объём {plan.tp1_size_pct}%)")
            row(self._t("confirm_tp2", "TP2"), f"{_fmt(plan.tp2_price)}  ({plan.tp2_offset_pct}%,  объём {plan.tp2_size_pct}%)")
            row(self._t("confirm_trailing", "Трейлинг стоп"),
                f"безубыток {_fmt(plan.breakeven_price)}  (активация {_fmt(plan.trailing_active_price)})")
