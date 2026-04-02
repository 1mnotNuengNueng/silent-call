from PyQt6.QtWidgets import QApplication
from ui.gui import MainWindow


def main():
    app = QApplication([])
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == '__main__':
    main()
