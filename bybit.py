#!/usr/bin/env python3
"""\
Bybit Futures Mini Terminal

Entry point for Bybit crypto exchange. Set up .env file!
"""

__part__     = 'Main script'
__author__   = "Sergey V Musenko"
__email__    = "sergey@musenko.com"
__copyright__= "© 2026, musenko.com"
__license__  = "MIT"
__credits__  = ["Sergey Musenko"]
__date__     = "2026-04-25"
__version__  = "0.1"
__status__   = "test"

import sys
import json
import os

from dotenv import load_dotenv
load_dotenv()

try:
    from PyQt6 import QtWidgets
    from PyQt6.QtGui import QIcon
except ImportError:
    from PyQt5 import QtWidgets
    from PyQt5.QtGui import QIcon

from src.ui.main_window import MainWindow
from src.api.bybit import BybitClient


def load_config():
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    app = QtWidgets.QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'bybit.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    config = load_config()
    config["window_title"] = "Bybit. Futures Mini Terminal"
    config.setdefault("ui", {})["exchange_url_template"] = "https://www.bybit.com/trade/usdt/{ticker}USDT"
    window = MainWindow(config, client_class=BybitClient)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
