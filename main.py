#!/usr/bin/env python3
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
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
