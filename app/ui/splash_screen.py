"""
Chronos - Splash Screen
Displays while the app is loading.
"""

from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont


class SplashScreen(QSplashScreen):
    """Modern splash screen for Chronos"""
    
    def __init__(self):
        # Create a pixmap for the splash
        pixmap = QPixmap(400, 300)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Draw the splash content
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 400, 300, 12, 12)
        
        # Border
        painter.setPen(QColor("#E4E4E7"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, 399, 299, 12, 12)
        
        # Title
        painter.setPen(QColor("#09090B"))
        font = QFont("IBM Plex Sans", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 100, 400, 50, Qt.AlignmentFlag.AlignCenter, "Chronos")
        
        # Subtitle
        painter.setPen(QColor("#71717A"))
        font = QFont("IBM Plex Sans", 12)
        painter.setFont(font)
        painter.drawText(0, 145, 400, 30, Qt.AlignmentFlag.AlignCenter, "Master your Time")
        
        # Loading text
        painter.setPen(QColor("#A1A1AA"))
        font = QFont("IBM Plex Sans", 10)
        painter.setFont(font)
        painter.drawText(0, 240, 400, 30, Qt.AlignmentFlag.AlignCenter, "Loading...")
        
        painter.end()
        
        super().__init__(pixmap)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
    
    def update_message(self, message: str):
        """Update the loading message"""
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#71717A")
        )
        QApplication.processEvents()
