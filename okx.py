#!/usr/bin/env python3
"""\
OKX Futures Mini Terminal

Entry point for OKX crypto exchange. Set up .env file!
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
from src.api.okx_client import OkxClient


def load_config():
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    app = QtWidgets.QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'okx.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    config = load_config()
    is_demo = os.environ.get("OKX_DEMO", "false").strip().lower() == "true"
    title = "OKX. Futures Mini Terminal"
    if is_demo:
        title += ". DEMO"
    config["window_title"] = title
    config["margin_mode_editable"] = True
    config.setdefault("ui", {})["exchange_url_template"] = "https://www.okx.com/trade-swap/{ticker_lower}-usdt-swap"
    window = MainWindow(config, client_class=OkxClient)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
