"""
Compatibility shim: ui_components
Provides stub components for main.py compatibility
"""
from PyQt6.QtWidgets import QLineEdit, QLabel, QPushButton, QWidget, QFrame
from PyQt6.QtCore import Qt


class SearchBar(QLineEdit):
    """Search bar component - passthrough to QLineEdit"""
    pass


class FilterChip(QLabel):
    """Filter chip component - passthrough to QLabel"""
    pass


class ToastNotification(QWidget):
    """Toast notification component - stub"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
    
    def show_toast(self, message, duration=3000):
        """Show toast notification - stub"""
        print(f"Toast: {message}")


class CustomButton(QPushButton):
    """Custom button component - passthrough to QPushButton"""
    pass


class CustomInput(QLineEdit):
    """Custom input component - passthrough to QLineEdit"""
    pass


class LoadingSpinner(QLabel):
    """Loading spinner component - stub"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Loading...")
    
    def start(self):
        self.show()
    
    def stop(self):
        self.hide()
