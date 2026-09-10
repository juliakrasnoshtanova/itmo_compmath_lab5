import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStyleFactory

from app import Lab5QtApp


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setFont(QFont("Helvetica Neue", 12))
    window = Lab5QtApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
