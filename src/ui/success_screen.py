import subprocess
import sys

try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt
    from PyQt6.QtCore import pyqtSignal as Signal
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtCore import pyqtSignal as Signal


class SuccessScreen(QtWidgets.QWidget):
    ok_clicked = Signal()

    def __init__(self, ui: dict = None, parent=None):
        super().__init__(parent)
        self._ui = ui or {}
        self._ticker = ""
        self._setup_ui()

    def _t(self, key, fallback=""):
        return self._ui.get(key, fallback)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 20)
        layout.setSpacing(20)

        success_label = QtWidgets.QLabel(self._t("success_title", "Success"))
        font = success_label.font()
        font.setBold(True)
        font.setPointSize(24)
        success_label.setFont(font)
        try:
            success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except AttributeError:
            success_label.setAlignment(Qt.AlignCenter)

        self._open_btn = QtWidgets.QPushButton(self._t("success_open_exchange", "Открыть терминал биржи"))
        self._open_btn.setMinimumWidth(200)
        self._open_btn.clicked.connect(self._open_exchange)

        ok_btn = QtWidgets.QPushButton(self._t("success_ok", "Ok"))
        ok_btn.setMinimumWidth(140)
        ok_btn.clicked.connect(self.ok_clicked)

        open_row = QtWidgets.QHBoxLayout()
        open_row.addStretch()
        open_row.addWidget(self._open_btn)
        open_row.addStretch()

        ok_row = QtWidgets.QHBoxLayout()
        ok_row.addStretch()
        ok_row.addWidget(ok_btn)
        ok_row.addStretch()

        layout.addStretch()
        layout.addWidget(success_label)
        layout.addLayout(open_row)
        layout.addStretch()
        layout.addLayout(ok_row)

    def set_ticker(self, ticker: str):
        self._ticker = ticker

    def _open_exchange(self):
        template = self._t("exchange_url_template", "https://www.bybit.com/trade/usdt/{ticker}USDT")
        url = template.format(ticker=self._ticker, ticker_lower=self._ticker.lower())
        subprocess.Popen(
            ["xdg-open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
