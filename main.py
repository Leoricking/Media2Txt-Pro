import os
import sys
import traceback
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMessageBox


APP_NAME = "Media2Txt Pro"
VERSION = "1.0.0"


def ensure_dirs():
    for folder in ("logs", "data", "models", "knowledge"):
        os.makedirs(folder, exist_ok=True)


def log(message: str):
    ensure_dirs()
    with open("logs/app.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {message}\n")


def exception_handler(exc_type, exc_value, exc_traceback):
    err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(err)
    log(err)
    try:
        QMessageBox.critical(None, "程式錯誤", str(exc_value))
    except Exception:
        pass


def main():
    sys.excepthook = exception_handler
    ensure_dirs()

    print("🚀 啟動中...")
    log("APP START")

    app = QApplication(sys.argv)

    from ui.main_window import MainWindow

    window = MainWindow()
    window.setWindowTitle(f"{APP_NAME} v{VERSION}")
    window.show()

    print("✅ UI 已啟動")
    log("UI SHOWN")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()