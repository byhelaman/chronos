"""
Chronos v2 - Login Dialog
Uses new auth_service and session_service (no encryption, no hardcoded secrets)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from supabase import Client
from typing import Optional, Dict

from app.services.auth_service import auth_service
from app.services.session_service import session_service


class LoginWorker(QThread):
    """Worker thread for authentication"""
    success = pyqtSignal(object, dict)
    error = pyqtSignal(str)
    
    def __init__(self, email: str, password: str):
        super().__init__()
        self.email = email
        self.password = password
    
    def run(self):
        try:
            supabase, user_info = auth_service.login(self.email, self.password)
            self.success.emit(supabase, user_info)
        except Exception as e:
            self.error.emit(str(e))


class LoginDialog(QDialog):
    """Login dialog for Chronos v2"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.supabase_client: Optional[Client] = None
        self.user_info: Dict = {}
        self._login_worker: Optional[LoginWorker] = None
        
        self.setWindowTitle("Chronos - Login")
        self.setFixedSize(400, 420)
        self.setModal(True)
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(15)
        
        # Header
        title = QLabel("Chronos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("IBM Plex Sans", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #09090B; margin-bottom: -4px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Master your Time")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("IBM Plex Sans", 11))
        subtitle.setStyleSheet("color: #71717A;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # Email
        email_label = QLabel("Email")
        email_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        layout.addWidget(email_label)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        self.email_input.setFixedHeight(36)
        self.email_input.returnPressed.connect(self._focus_password)
        layout.addWidget(self.email_input)
        
        # Password
        pass_label = QLabel("Password")
        pass_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        layout.addWidget(pass_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(36)
        self.password_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.password_input)
        
        # Remember me
        self.remember_checkbox = QCheckBox("Remember me for 7 days")
        self.remember_checkbox.setFont(QFont("IBM Plex Sans", 10))
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.remember_checkbox)
        
        layout.addSpacing(16)
        
        # Login button
        self.login_button = QPushButton("Sign In")
        self.login_button.setFont(QFont("IBM Plex Sans", 11, QFont.Weight.Medium))
        self.login_button.setFixedHeight(36)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._on_login)
        layout.addWidget(self.login_button)
        
        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #dc2626; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        layout.addStretch()
    
    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                color: #09090B;
            }
            QLineEdit:focus { border: 1px solid #18181B; }
            QLineEdit::placeholder { color: #A1A1AA; }
            QPushButton {
                background-color: #18181B;
                color: #FAFAFA;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #27272A; }
            QPushButton:disabled { background-color: #a1a1aa; }
            QLabel { color: #09090B; }
            QCheckBox { spacing: 8px; }
        """)
    
    def _focus_password(self):
        self.password_input.setFocus()
    
    def _on_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or "@" not in email:
            self._show_error("Please enter a valid email")
            return
        
        if not password:
            self._show_error("Password is required")
            return
        
        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in...")
        self.error_label.setVisible(False)
        
        self._login_worker = LoginWorker(email, password)
        self._login_worker.success.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._login_worker.start()
    
    def _on_login_success(self, supabase: Client, user_info: Dict):
        self.supabase_client = supabase
        self.user_info = user_info
        
        if self.remember_checkbox.isChecked():
            session_service.save_session(supabase, user_info)
        
        self.accept()
    
    def _on_login_error(self, error_message: str):
        self.login_button.setEnabled(True)
        self.login_button.setText("Sign In")
        self._show_error(error_message)
    
    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.setVisible(True)
    
    def closeEvent(self, event):
        if not self.supabase_client:
            self.reject()
        event.accept()
