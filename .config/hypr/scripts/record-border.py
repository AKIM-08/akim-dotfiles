#!/usr/bin/env python3
"""
record-border.py - Lightweight click-through red border overlay for screen recording in Hyprland
"""
import sys

def run():
    if len(sys.argv) < 5:
        sys.exit(0)

    try:
        from PyQt5.QtWidgets import QApplication, QWidget
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPainter, QPen, QColor
        has_qt5 = True
    except ImportError:
        try:
            from PyQt6.QtWidgets import QApplication, QWidget
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QPainter, QPen, QColor
            has_qt5 = False
        except ImportError:
            sys.exit(0)

    class BorderOverlay(QWidget):
        def __init__(self, x, y, w, h):
            super().__init__()
            self.setObjectName("record-border")
            self.setWindowTitle("record-border")
            self.setGeometry(x, y, w, h)
            
            flags = (
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool |
                Qt.X11BypassWindowManagerHint
            )
            if hasattr(Qt, "WindowTransparentForInput"):
                flags |= Qt.WindowTransparentForInput
            self.setWindowFlags(flags)
            
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            # 2.5px crisp red border (with glow outline)
            pen = QPen(QColor(255, 51, 102, 235))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(1, 1, self.width() - 2, self.height() - 2)

    app = QApplication(sys.argv)
    app.setApplicationName("record-border")
    x = int(sys.argv[1])
    y = int(sys.argv[2])
    w = int(sys.argv[3])
    h = int(sys.argv[4])
    overlay = BorderOverlay(x, y, w, h)
    overlay.show()
    sys.exit(app.exec_() if has_qt5 else app.exec())

if __name__ == '__main__':
    run()
