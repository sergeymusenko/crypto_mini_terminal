try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt, QRegularExpression, QObject, QEvent, QTimer
    from PyQt6.QtGui import QKeySequence, QColor, QRegularExpressionValidator
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt, QRegularExpression, QObject, QEvent, QTimer
    from PyQt5.QtGui import QKeySequence, QColor, QRegularExpressionValidator

import math

from src.logic.validator import validate_inputs, ValidationError
from src.logic.calculator import calculate
from src.ui.confirmation_screen import ConfirmationScreen
from src.ui.success_screen import SuccessScreen
from src.logger import log_order

class _EnterFilter(QObject):
    """Move focus to the next widget in tab order when Enter/Return is pressed."""
    def eventFilter(self, obj, event):
        try:
            is_key_press = event.type() == QEvent.Type.KeyPress
        except AttributeError:
            is_key_press = event.type() == QEvent.KeyPress
        if not is_key_press:
            return super().eventFilter(obj, event)
        try:
            is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        except AttributeError:
            is_enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        if is_enter:
            obj.focusNextChild()
            return True
        return super().eventFilter(obj, event)


_DIRECTION_COLORS = {
    "LONG": "#2ea043",
    "SHORT": "#e5534b",
}

_FIELD_WIDGETS = {
    "symbol":            "ticker_input",
    "direction":         "direction_combo",
    "position_size":     "position_size_input",
    "leverage":          "leverage_input",
    "entry_price":       "entry_price_input",
    "stop_loss_pct":     "stop_loss_input",
    "final_tp_pct":      "final_tp_input",
    "tp1_size_pct":      "tp1_size_input",
    "tp2_size_pct":      "tp2_size_input",
    "tp1_offset_pct":    "tp1_offset_input",
    "tp2_offset_pct":    "tp2_offset_input",
    "trailing_stop_pct": "trailing_stop_input",
}


class MainWindow(QtWidgets.QWidget):
    def __init__(self, config, client_class):
        super().__init__()
        self.config = config
        self._ui = config.get("ui", {})
        self._client_class = client_class
        self._setup_ui()

    def _t(self, key, fallback=""):
        return self._ui.get(key, fallback)

    def _setup_ui(self):
        self.setWindowTitle(self.config.get("window_title", "Futures Mini Terminal"))

        try:
            ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            ALIGN_LEFT  = Qt.AlignmentFlag.AlignLeft  | Qt.AlignmentFlag.AlignVCenter
            ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
        except AttributeError:
            ALIGN_RIGHT  = Qt.AlignRight | Qt.AlignVCenter
            ALIGN_LEFT   = Qt.AlignLeft  | Qt.AlignVCenter
            ALIGN_CENTER = Qt.AlignCenter

        # Single shared QGridLayout — all rows share the same column widths:
        #   col 0 — row labels       (right-aligned, no stretch)
        #   col 1 — left sublabels   (right-aligned, no stretch)
        #   col 2 — left input       (stretch 1)  ← right edge = alignment axis
        #   col 3 — right sublabels  (right-aligned, no stretch)
        #   col 4 — right input      (stretch 1)
        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.setColumnStretch(2, 1)
        form.setColumnStretch(4, 1)

        r = 0  # current grid row

        # --- Row 0: Direction (spans cols 1-2) + Margin type ---
        self.direction_combo = QtWidgets.QComboBox()
        directions = self._ui.get("direction_options", ["LONG", "SHORT"])
        for i, text in enumerate(directions):
            self.direction_combo.addItem(text)
            color = _DIRECTION_COLORS.get(text)
            if color:
                try: role = Qt.ItemDataRole.ForegroundRole
                except AttributeError: role = Qt.ForegroundRole
                self.direction_combo.setItemData(i, QColor(color), role)
        bold_font = self.direction_combo.font()
        bold_font.setBold(True)
        self.direction_combo.setFont(bold_font)
        self.direction_combo.setCurrentText(self.config.get("direction", "LONG"))
        self.direction_combo.currentTextChanged.connect(self._update_direction_color)
        self._update_direction_color(self.direction_combo.currentText())

        if self.config.get("margin_mode_editable", False):
            self.margin_type_combo = QtWidgets.QComboBox()
            for opt in [self._t("margin_isolated", "Isolated"), self._t("margin_cross", "Cross")]:
                self.margin_type_combo.addItem(opt)
            margin_widget = self.margin_type_combo
        else:
            self.margin_type_label = QtWidgets.QLineEdit(self._t("margin_type_default", "—"))
            self.margin_type_label.setReadOnly(True)
            try:
                self.margin_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            except AttributeError:
                self.margin_type_label.setAlignment(Qt.AlignCenter)
            margin_widget = self.margin_type_label

        form.addWidget(QtWidgets.QLabel(self._t("direction_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(self.direction_combo, r, 1, 1, 2)  # spans cols 1-2 = same width as "sublabel + left-input"
        form.addWidget(QtWidgets.QLabel(self._t("margin_type_sublabel", "Маржа")), r, 3, ALIGN_RIGHT)
        form.addWidget(margin_widget, r, 4)
        r += 1

        # --- Row 1: Ticker (spans cols 1-4, full width) ---
        self.ticker_input = QtWidgets.QLineEdit()
        self.ticker_input.setPlaceholderText(self._t("ticker_placeholder", "BTC, ETH, ..."))
        self.ticker_input.setAlignment(ALIGN_LEFT)
        self.ticker_input.setMaxLength(20) # ограничить длину 20 знаков

        # Валидатор: ПЕРВЫМ знаком должна быть буква, далее латиница, цифры и подчерк
        ticker_regex = QRegularExpression(r"^[A-Za-z][A-Za-z0-9_]*$")
        ticker_validator = QRegularExpressionValidator(ticker_regex, self.ticker_input)
        self.ticker_input.setValidator(ticker_validator)

        # Сразу переводить буквы в верхний регистр
        self.ticker_input.textChanged.connect(lambda text: self.ticker_input.setText(text.upper()))

        form.addWidget(QtWidgets.QLabel(self._t("ticker_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(self.ticker_input, r, 1, 1, 4)  # spans cols 1-4
        r += 1

        # --- Row 2: Position size (col 2) + Leverage (col 4) ---
        self.position_size_input = QtWidgets.QDoubleSpinBox()
        self.position_size_input.setRange(0.01, 100_000)
        self.position_size_input.setValue(self.config.get("position_size", 25.0))
        self._style_float_field(self.position_size_input)

        self.leverage_input = QtWidgets.QDoubleSpinBox()
        self.leverage_input.setRange(1, 125)
        self.leverage_input.setValue(self.config.get("leverage", 10.0))
        self._style_float_field(self.leverage_input)

        form.addWidget(QtWidgets.QLabel(self._t("size_leverage_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(QtWidgets.QLabel(self._t("size_sublabel")), r, 1, ALIGN_RIGHT)
        form.addWidget(self.position_size_input, r, 2)
        form.addWidget(QtWidgets.QLabel(self._t("leverage_sublabel")), r, 3, ALIGN_RIGHT)
        form.addWidget(self.leverage_input, r, 4)
        r += 1

        # --- Row 3: Entry price (spans cols 1-2) + hint (spans cols 3-4) ---
        self.entry_price_input = QtWidgets.QLineEdit("0")
        self.entry_price_input.setAlignment(ALIGN_RIGHT)
        self.entry_price_input.setMaxLength(20) # Ограничение ввода максимум 20 знаков
        _orig_focus = self.entry_price_input.focusInEvent
        def _price_focus(e):
            _orig_focus(e)
            QTimer.singleShot(0, self.entry_price_input.selectAll)
        self.entry_price_input.focusInEvent = _price_focus

        # Валидатор: только цифры и одна точка, без лидирующих нулей (кроме 0.х)
        regex = QRegularExpression(r"^(0|[1-9]\d*)?(\.\d*)?$")
        validator = QRegularExpressionValidator(regex, self.entry_price_input)
        self.entry_price_input.setValidator(validator)

        form.addWidget(QtWidgets.QLabel(self._t("entry_price_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(self.entry_price_input, r, 1, 1, 2)  # spans cols 1-2
        form.addWidget(QtWidgets.QLabel(self._t("entry_price_market_label", "0 - рыночная")), r, 3, 1, 2, ALIGN_LEFT)
        r += 1

        # --- Row 4: Stop loss (spans cols 1-2) ---
        self.stop_loss_input = QtWidgets.QDoubleSpinBox()
        self.stop_loss_input.setRange(0.01, 100)
        self.stop_loss_input.setValue(self.config.get("stop_loss_pct", 1.0))
        self._style_float_field(self.stop_loss_input)

        form.addWidget(QtWidgets.QLabel(self._t("stop_loss_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(self.stop_loss_input, r, 1, 1, 2)  # spans cols 1-2
        r += 1

        # --- Row 5: Final TP (spans cols 1-2) ---
        self.final_tp_input = QtWidgets.QDoubleSpinBox()
        self.final_tp_input.setRange(0.01, 10_000)
        self.final_tp_input.setValue(self.config.get("final_tp_pct", 5.0))
        self._style_float_field(self.final_tp_input)

        form.addWidget(QtWidgets.QLabel(self._t("final_tp_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(self.final_tp_input, r, 1, 1, 2)  # spans cols 1-2
        r += 1

        # --- Row 6: TP1 ---
        self.tp1_size_input = QtWidgets.QDoubleSpinBox()
        self.tp1_size_input.setRange(0.01, 99.)
        self.tp1_size_input.setValue(self.config.get("tp1_size_pct", 5.0))
        self._style_float_field(self.tp1_size_input)
        self.tp1_offset_input = QtWidgets.QDoubleSpinBox()
        self.tp1_offset_input.setRange(0., 100.)
        self.tp1_offset_input.setValue(self.config.get("tp1_offset_pct", 5.0))
        self._style_float_field(self.tp1_offset_input)

        form.addWidget(QtWidgets.QLabel(self._t("tp1_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(QtWidgets.QLabel(self._t("tp1_size_sublabel")), r, 1, ALIGN_RIGHT)
        form.addWidget(self.tp1_size_input, r, 2)
        form.addWidget(QtWidgets.QLabel(self._t("tp1_offset_sublabel")), r, 3, ALIGN_RIGHT)
        form.addWidget(self.tp1_offset_input, r, 4)
        r += 1

        # --- Row 7: TP2 ---
        self.tp2_size_input = QtWidgets.QDoubleSpinBox()
        self.tp2_size_input.setRange(0.01, 99.)
        self.tp2_size_input.setValue(self.config.get("tp2_size_pct", 5.0))
        self._style_float_field(self.tp2_size_input)
        self.tp2_offset_input = QtWidgets.QDoubleSpinBox()
        self.tp2_offset_input.setRange(0., 100.)
        self.tp2_offset_input.setValue(self.config.get("tp2_offset_pct", 5.0))
        self._style_float_field(self.tp2_offset_input)

        form.addWidget(QtWidgets.QLabel(self._t("tp2_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(QtWidgets.QLabel(self._t("tp2_size_sublabel")), r, 1, ALIGN_RIGHT)
        form.addWidget(self.tp2_size_input, r, 2)
        form.addWidget(QtWidgets.QLabel(self._t("tp2_offset_sublabel")), r, 3, ALIGN_RIGHT)
        form.addWidget(self.tp2_offset_input, r, 4)
        r += 1

        # --- Row 8: Trailing stop activation offset (editable; distance is auto-calculated from fee_rate_pct) ---
        self.trailing_stop_input = QtWidgets.QDoubleSpinBox()
        self.trailing_stop_input.setRange(0.001, 100)
        self.trailing_stop_input.setValue(self.config.get("tp1_offset_pct", 1.5))
        self._style_float_field(self.trailing_stop_input)
        # auto-fill from TP1 offset, but stays editable
        self.tp1_offset_input.valueChanged.connect(self.trailing_stop_input.setValue)

        form.addWidget(QtWidgets.QLabel(self._t("trailing_stop_label")), r, 0, ALIGN_RIGHT)
        form.addWidget(QtWidgets.QLabel(self._t("tp1_offset_sublabel", "Отступ %")), r, 3, ALIGN_RIGHT)
        form.addWidget(self.trailing_stop_input, r, 4)
        r += 1

        # Submit button
        self.submit_btn = QtWidgets.QPushButton(self._t("submit_button", "Preview"))
        self.submit_btn.setMinimumWidth(140)
        self.submit_btn.clicked.connect(self._on_submit)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(); btn_row.addWidget(self.submit_btn); btn_row.addStretch()

        # Error label shown above the submit button
        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setAlignment(ALIGN_CENTER)
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(self.error_label.fontMetrics().height())

        # Esc to close (Логика теперь вынесена в keyPressEvent для проверки фокуса)

        # Wrap form + error + button so they can be hidden together during confirmation
        self._form_widget = QtWidgets.QWidget()
        form_outer = QtWidgets.QVBoxLayout(self._form_widget)
        form_outer.setContentsMargins(0, 0, 0, 0)
        form_outer.setSpacing(12)
        form_outer.addLayout(form)
        form_outer.addWidget(self.error_label)
        form_outer.addLayout(btn_row)

        # Confirmation screen (hidden until submit succeeds)
        self._confirmation = ConfirmationScreen(ui=self._ui)
        self._confirmation.confirmed.connect(self._on_confirmed)
        self._confirmation.cancelled.connect(self._on_cancelled)
        self._confirmation.hide()

        # Success screen (hidden until order is placed successfully)
        self._success_screen = SuccessScreen(ui=self._ui)
        self._success_screen.ok_clicked.connect(self._on_success_ok)
        self._success_screen.hide()

        # Assemble main layout
        main = QtWidgets.QVBoxLayout()
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(12)
        main.addWidget(self._form_widget)
        main.addWidget(self._confirmation)
        main.addWidget(self._success_screen)
        self.setLayout(main)
        self.setMinimumWidth(480)

        # Explicit tab order: top-to-bottom, left-to-right
        _tab = [
            self.direction_combo,
            self.ticker_input,
            self.position_size_input, self.leverage_input,
            self.entry_price_input,
            self.stop_loss_input, self.final_tp_input,
            self.tp1_size_input, self.tp1_offset_input,
            self.tp2_size_input, self.tp2_offset_input,
            self.trailing_stop_input,
            self.submit_btn,
        ]
        for i in range(len(_tab) - 1):
            QtWidgets.QWidget.setTabOrder(_tab[i], _tab[i + 1])

        # Enter key moves focus to the next field (skip combos — they handle Enter themselves)
        self._enter_filter = _EnterFilter(self)
        for w in [
            self.ticker_input,
            self.position_size_input, self.leverage_input,
            self.entry_price_input,
            self.stop_loss_input, self.final_tp_input,
            self.tp1_size_input, self.tp1_offset_input,
            self.tp2_size_input, self.tp2_offset_input,
            self.trailing_stop_input,
        ]:
            w.installEventFilter(self._enter_filter)

        # При запуске приложения ни одно поле не должно быть в фокусе
        self.setFocus()

        # Fetch actual margin mode from exchange after window appears
        QTimer.singleShot(0, self._fetch_margin_mode)

    def _fetch_margin_mode(self):
        if self.config.get("margin_mode_editable", False):
            return  # user selects margin mode manually
        try:
            mode = self._client_class().get_margin_mode()
            display = {
                "cross":    self._t("margin_cross",    "Cross"),
                "isolated": self._t("margin_isolated", "Isolated"),
            }.get(mode.lower(), mode)
            self.margin_type_label.setText(display)
        except Exception:
            self.margin_type_label.setText(self._t("margin_type_unavailable", "н/д"))

    def keyPressEvent(self, event):
        """Реализация логики Esc: убрать фокус или закрыть приложение."""
        try:
            esc_key = Qt.Key.Key_Escape
        except AttributeError:
            esc_key = Qt.Key_Escape

        if event.key() == esc_key:
            focused_widget = self.focusWidget()
            # Если какой-то виджет (поле ввода и т.д.) в фокусе — снимаем его
            if focused_widget is not None and focused_widget is not self:
                focused_widget.clearFocus()
            else:
                # Если фокуса на полях нет — закрываем окно
                self.close()
        else:
            super().keyPressEvent(event)

    def _style_float_field(self, sb):
        sb.setDecimals(2)
        try:
            sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            sb.lineEdit().setAlignment(Qt.AlignmentFlag.AlignRight)
        except AttributeError:
            sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            sb.lineEdit().setAlignment(Qt.AlignRight)
        sb.setStyleSheet("padding-right: 2px;")

    def _update_direction_color(self, text):
        color = _DIRECTION_COLORS.get(text, "")
        self.direction_combo.setStyleSheet(f"QComboBox {{ color: {color}; }}")

    def _restore_submit_btn(self):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText(self._t("submit_button", "Preview"))

    def _show_confirmation(self, plan):
        self._current_plan = plan
        self.error_label.setText("")
        self._form_widget.hide()
        self._confirmation.set_plan(plan)
        self._confirmation.show()
        # Button stays disabled while confirmation is visible

    def _on_confirmed(self):
        log_order(self._current_plan)
        self._confirmation.hide()
        try:
            client = self._client_class()
            client.place_orders(self._current_plan, dry_run=False)
            self._show_success(self._current_plan.symbol)
        except Exception as e:
            self._form_widget.show()
            self._restore_submit_btn()
            self._show_error(str(e))

    def _show_success(self, symbol: str):
        ticker = symbol[:-4] if symbol.endswith("USDT") else symbol
        self._success_screen.set_ticker(ticker)
        self._success_screen.show()

    def _on_success_ok(self):
        self._success_screen.hide()
        self._form_widget.show()
        self._restore_submit_btn()

    def _on_cancelled(self):
        self._confirmation.hide()
        self._form_widget.show()
        self._restore_submit_btn()

    def _show_error(self, text, field=None):
        self.error_label.setText(text)
        if field and field in _FIELD_WIDGETS:
            widget = getattr(self, _FIELD_WIDGETS[field])
            widget.setFocus()
            if hasattr(widget, "selectAll"):
                widget.selectAll()

    def _collect_data(self) -> dict:
        """Collect all form values into a plain dict for validator/calculator."""
        ticker = self.ticker_input.text().strip().upper()
        symbol = (ticker + "USDT") if ticker and not ticker.endswith("USDT") else ticker
        entry_text = self.entry_price_input.text().strip()
        try:
            entry_price = float(entry_text) if entry_text else 0.0
        except ValueError:
            entry_price = 0.0
        return {
            "symbol": symbol,
            "direction": self.direction_combo.currentText(),
            "margin_type": self.margin_type_combo.currentText() if hasattr(self, "margin_type_combo") else self.margin_type_label.text(),
            "position_size": self.position_size_input.value(),
            "leverage": self.leverage_input.value(),
            "entry_price": entry_price,
            "is_market": entry_price == 0,
            "stop_loss_pct": self.stop_loss_input.value(),
            "final_tp_pct": self.final_tp_input.value(),
            "tp1_size_pct": self.tp1_size_input.value(),
            "tp1_offset_pct": self.tp1_offset_input.value(),
            "tp2_size_pct": self.tp2_size_input.value(),
            "tp2_offset_pct": self.tp2_offset_input.value(),
            "trailing_distance_pct": self.trailing_stop_input.value(),
            "fee_rate_pct": self.config.get("fee_rate_pct", 0.075),
            "hedge_mode": self.config.get("hedge_mode", False),
        }

    def _on_submit(self):
        self.error_label.setText("")

        data = self._collect_data()

        # Local validation before hitting the API
        try:
            validate_inputs(data)
        except ValidationError as e:
            self._show_error(str(e), field=e.field)
            return

        self.submit_btn.clearFocus()
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText(self._t("submit_loading", "..."))
        success = False
        try:
            client = self._client_class()

            # Validate ticker exists on Bybit
            try:
                instrument = client.validate_ticker(data["symbol"])
            except Exception:
                self._show_error(
                    self._t("error_invalid_ticker", "Тикер {symbol} не найден на Bybit")
                    .format(symbol=data["symbol"]),
                    field="symbol",
                )
                return

            # Check leverage against exchange maximum
            max_lev_raw = instrument.get("leverageFilter", {}).get("maxLeverage")
            if max_lev_raw:
                max_lev = float(max_lev_raw)
                if data["leverage"] > max_lev:
                    self._show_error(
                        self._t("error_leverage_too_high", "Плечо {lev}x превышает максимум {max}x для {symbol}")
                        .format(lev=int(data["leverage"]), max=int(max_lev), symbol=data["symbol"]),
                        field="leverage",
                    )
                    return

            # Reject if same-direction position already open (hedging opposite side is allowed)
            existing_side = client.get_open_position_side(data["symbol"])
            if existing_side == data["direction"]:
                self._show_error(
                    self._t("error_position_exists", "По {symbol} уже открыта позиция {side}. Закройте её перед входом.")
                    .format(symbol=data["symbol"], side=existing_side),
                    field="symbol",
                )
                return

            # Resolve market price internally — do not write back to the form
            if data["is_market"]:
                data["entry_price"] = client.get_last_price(data["symbol"])

            # Lot size constraints from exchange
            lot           = instrument.get("lotSizeFilter", {})
            min_qty           = float(lot.get("minOrderQty",       0) or 0)
            qty_step          = float(lot.get("qtyStep",           0) or 0)
            min_notional_value = float(lot.get("minNotionalValue", 0) or 0)

            qty = data["position_size"] / data["entry_price"]  # position_size is notional in USDT
            position_size_rounded = False

            # Round qty to exchange step size
            if qty_step > 0:
                rounded_qty = math.floor(qty / qty_step) * qty_step
                if min_qty > 0 and rounded_qty < min_qty:
                    rounded_qty = math.ceil(qty / qty_step) * qty_step
                rounded_qty = round(rounded_qty, 10)  # remove floating point noise
                if abs(rounded_qty - qty) > qty_step * 1e-9:
                    position_size_rounded = True
                    data["position_size"] = round(rounded_qty * data["entry_price"], 8)
                    qty = rounded_qty

            # Minimum quantity in coins
            if min_qty > 0 and qty < min_qty:
                min_notional = min_qty * data["entry_price"]
                self._show_error(
                    self._t("error_min_order_qty", "Объём позиции слишком мал.")
                    .format(min_qty=min_qty, min_notional=min_notional),
                    field="position_size",
                )
                return

            # Minimum notional value in USDT
            if min_notional_value > 0 and data["position_size"] < min_notional_value:
                self._show_error(
                    self._t("error_min_notional", "Минимальная сумма позиции: {min_val:.2f} USDT")
                    .format(min_val=min_notional_value),
                    field="position_size",
                )
                return

            data["position_size_rounded"] = position_size_rounded
            data["qty_step"] = qty_step

            # Check USDT balance vs required margin
            balance = client.get_available_balance()
            margin_needed = data["position_size"] / data["leverage"]
            if balance < margin_needed:
                self._show_error(
                    self._t("error_insufficient_funds", "Недостаточно средств: нужно {needed:.2f} USDT, доступно {available:.2f} USDT")
                    .format(needed=margin_needed, available=balance)
                )
                return

            # Calculate SL/TP prices and show confirmation
            plan = calculate(data)
            self._show_confirmation(plan)
            success = True

        except ValidationError as e:
            self._show_error(str(e), field=e.field)
        except Exception as e:
            self._show_error(str(e))
        finally:
            if not success:
                self._restore_submit_btn()
