#!/usr/bin/env python3
import sys
import json
import os

from dotenv import load_dotenv
load_dotenv()

try:
    from PyQt6 import QtWidgets
except ImportError:
    from PyQt5 import QtWidgets

from src.ui.main_window import MainWindow


def load_config():
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    app = QtWidgets.QApplication(sys.argv)
    config = load_config()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
