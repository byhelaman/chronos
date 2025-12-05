"""
Chronos v2 - Login Dialog
Uses new auth_service and session_service (no encryption, no hardcoded secrets)
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from supabase import Client
from typing import Optional, Dict

from app.services.auth_service import auth_service
from app.services.session_service import session_service
from app.config import config


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
        self.setFixedSize(400, 500)
        self.setModal(True)
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "favicon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        
        # Header (Grouped for tighter spacing)
        header_container = QWidget()
        header_container.setFixedHeight(60)
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        
        title = QLabel("Chronos")
        title.setFont(QFont("IBM Plex Sans", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #09090B;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Master your Time")
        subtitle.setFont(QFont("IBM Plex Sans", 11))
        subtitle.setStyleSheet("color: #71717A;")
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header_container)
        layout.addSpacing(32)
        
        # Email
        email_label = QLabel("Email")
        email_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        layout.addWidget(email_label)
        
        # Email Container (Input + Error)
        email_container = QWidget()
        email_layout = QVBoxLayout(email_container)
        email_layout.setContentsMargins(0, 0, 0, 0)
        email_layout.setSpacing(4)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        self.email_input.setFixedHeight(40)
        self.email_input.returnPressed.connect(self._focus_password)
        email_layout.addWidget(self.email_input)
        
        # Email Error
        self.email_error = QLabel("")
        self.email_error.setStyleSheet("color: #dc2626; font-size: 12px; margin-top: 4px;")
        self.email_error.setVisible(False)
        email_layout.addWidget(self.email_error)
        
        layout.addWidget(email_container)
        layout.addSpacing(8)
        
        # Password
        pass_label = QLabel("Password")
        pass_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        layout.addWidget(pass_label)
        
        # Password Container (Input + Error)
        pass_container = QWidget()
        pass_layout = QVBoxLayout(pass_container)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(4)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(40)
        self.password_input.returnPressed.connect(self._on_login)
        pass_layout.addWidget(self.password_input)
        
        # Password Error
        self.password_error = QLabel("")
        self.password_error.setStyleSheet("color: #dc2626; font-size: 12px; margin-top: 4px;")
        self.password_error.setVisible(False)
        pass_layout.addWidget(self.password_error)
        
        layout.addWidget(pass_container)
        
        # Remember me
        self.remember_checkbox = QCheckBox("Remember me for 7 days")
        self.remember_checkbox.setFont(QFont("IBM Plex Sans", 10))
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.remember_checkbox)
        
        layout.addSpacing(24)
        
        # General Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #dc2626; font-size: 13px; font-weight: 500;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        # Login button
        self.login_button = QPushButton("Sign In")
        self.login_button.setFont(QFont("IBM Plex Sans", 11, QFont.Weight.Medium))
        self.login_button.setFixedHeight(40)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._on_login)
        layout.addWidget(self.login_button)
        
        layout.addStretch()
        
        # Connect validation signals after all widgets are created
        self.email_input.textChanged.connect(self._validate_email)
        self.password_input.textChanged.connect(self._validate_password)
        
        # Pre-fill with last used email
        if config.last_email:
            self.email_input.setText(config.last_email)
    
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
    
    def _validate_email(self):
        # Hide API error when user starts typing
        self.error_label.setVisible(False)
        
        email = self.email_input.text().strip()
        if not email:
            self.email_error.setText("Email is required")
            self.email_error.setVisible(True)
            return False
        elif "@" not in email or "." not in email:
            self.email_error.setText("Please enter a valid email")
            self.email_error.setVisible(True)
            return False
        else:
            self.email_error.setVisible(False)
            return True

    def _validate_password(self):
        # Hide API error when user starts typing
        self.error_label.setVisible(False)
        
        password = self.password_input.text()
        if not password:
            self.password_error.setText("Password is required")
            self.password_error.setVisible(True)
            return False
        else:
            self.password_error.setVisible(False)
            return True

    def _on_login(self):
        # Validate all
        is_email_valid = self._validate_email()
        is_pass_valid = self._validate_password()
        
        if not is_email_valid or not is_pass_valid:
            return
        
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
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
        
        # Save email for next login
        email = self.email_input.text().strip()
        config.save_email(email)
        
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
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    
    def closeEvent(self, event):
        if not self.supabase_client:
            self.reject()
        event.accept()
