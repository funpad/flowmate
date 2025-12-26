import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon 
from ui.main_window import FlowMate

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/logo.png"))

    # 【新增】关键设置：关闭所有窗口后，程序依然保持运行（驻留在托盘）
    app.setQuitOnLastWindowClosed(False)

    window = FlowMate()
    window.show()
    sys.exit(app.exec())