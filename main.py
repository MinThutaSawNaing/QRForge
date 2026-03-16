import sys
import ctypes

from PyQt6.QtWidgets import QApplication

from qr_maker_app import QRMakerWindow, create_app_icon


def main() -> int:
    if sys.platform == "win32":
        app_id = "QRForge.Desktop"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication(sys.argv)
    app.setApplicationName("QRForge")
    app.setWindowIcon(create_app_icon())

    window = QRMakerWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
