try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtCore import pyqtSignal as Signal
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt, QUrl
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtCore import pyqtSignal as Signal


class SuccessScreen(QtWidgets.QWidget):
    ok_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ticker = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 20)
        layout.setSpacing(20)

        success_label = QtWidgets.QLabel("Success")
        font = success_label.font()
        font.setBold(True)
        font.setPointSize(24)
        success_label.setFont(font)
        try:
            success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except AttributeError:
            success_label.setAlignment(Qt.AlignCenter)

        self._open_btn = QtWidgets.QPushButton("Открыть терминал биржи")
        self._open_btn.setMinimumWidth(200)
        self._open_btn.clicked.connect(self._open_exchange)

        ok_btn = QtWidgets.QPushButton("Ok")
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
        symbol = self._ticker if self._ticker.endswith("USDT") else self._ticker + "USDT"
        url = f"https://www.bybit.com/trade/usdt/{symbol}"
        QDesktopServices.openUrl(QUrl(url))
