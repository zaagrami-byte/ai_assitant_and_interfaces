import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Accueil vocal ISIMM")
    parser.add_argument("--sans-camera", action="store_true")
    args = parser.parse_args()
    from PySide6.QtWidgets import QApplication
    from .gui import Window, STYLE
    from .config import Settings

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(STYLE)
    window = Window(Settings.load(), args.sans_camera)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
