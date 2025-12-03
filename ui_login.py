"""
Chronos - Login Dialog
Interfaz de autenticación con Supabase Auth
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QWidget, QCheckBox, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon
from auth_manager import auth_manager
from config_manager import config_manager
from session_manager import session_manager
from supabase import Client
from typing import Optional, Dict
import utils
from theme_manager import theme
from ui_components import CustomButton, CustomInput, LoadingSpinner


def show_message(parent, title, text, icon, buttons=QMessageBox.StandardButton.Ok):
    """Helper para mostrar alertas con estilos consistentes"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    
    # Resize Icon (Reducir tamaño a 32x32)
    icon_map = {
        QMessageBox.Icon.Information: QStyle.StandardPixmap.SP_MessageBoxInformation,
        QMessageBox.Icon.Warning: QStyle.StandardPixmap.SP_MessageBoxWarning,
        QMessageBox.Icon.Critical: QStyle.StandardPixmap.SP_MessageBoxCritical,
        QMessageBox.Icon.Question: QStyle.StandardPixmap.SP_MessageBoxQuestion,
    }
    
    standard_pixmap = icon_map.get(icon)
    if standard_pixmap:
        pixmap = msg.style().standardIcon(standard_pixmap).pixmap(32, 32)
        msg.setIconPixmap(pixmap)
    else:
        msg.setIcon(icon)

    msg.setStandardButtons(buttons)
    msg.setStyleSheet(theme.messagebox_style())
    
    
    # Botones Primarios (Ok, Yes, Save) - estilo compacto
    primary_buttons = [
        QMessageBox.StandardButton.Yes,
        QMessageBox.StandardButton.Ok,
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.Retry
    ]
    
    for btn_type in primary_buttons:
        if buttons & btn_type:
            btn = msg.button(btn_type)
            if btn:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #18181B;
                        color: #FAFAFA;
                        border: 1px solid #18181B;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #27272A;
                        border: 1px solid #27272A;
                    }
                    QPushButton:pressed {
                        background-color: #09090B;
                        border: 1px solid #09090B;
                    }
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                
    # Botones Secundarios (Cancel, No, Close) - estilo compacto
    secondary_buttons = [
        QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Close,
        QMessageBox.StandardButton.Abort,
        QMessageBox.StandardButton.Ignore
    ]
    
    for btn_type in secondary_buttons:
        if buttons & btn_type:
            btn = msg.button(btn_type)
            if btn:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #09090B;
                        border: 1px solid #E4E4E7;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #F4F4F5;
                        border: 1px solid #E4E4E7;
                    }
                    QPushButton:pressed {
                        background-color: #E4E4E7;
                        border: 1px solid #E4E4E7;
                    }
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

    return msg.exec()


class LoginWorker(QThread):
    """Worker thread para autenticación sin bloquear UI"""
    success = pyqtSignal(object, dict)  # supabase_client, user_info
    error = pyqtSignal(str)
    
    def __init__(self, email: str, password: str):
        super().__init__()
        self.email = email
        self.password = password
    
    def run(self):
        try:
            supabase, user_info = auth_manager.login(self.email, self.password)
            self.success.emit(supabase, user_info)
        except Exception as e:
            self.error.emit(str(e))


class LoginDialog(QDialog):
    """Diálogo de autenticación para Chronos"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.supabase_client: Optional[Client] = None
        self.config: Dict[str, str] = {}
        self.user_info: Dict = {}
        self._login_worker: Optional[LoginWorker] = None
        self._loading_spinner: Optional[LoadingSpinner] = None
        
        self.setWindowTitle("Chronos - Login")
        self.setFixedSize(400, 450)  # Tamaño más conservador
        self.setModal(True)
        self.setWindowIcon(QIcon(utils.resource_path("favicon.ico")))
        
        self._setup_ui()
        self._apply_styles()    
    
    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(15)  # Spacing original
        
        # Header (Title + Subtitle)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Chronos")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("IBM Plex Sans", 22, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setMinimumHeight(40)
        title_label.setStyleSheet("margin-bottom: -4px; color: #09090B;")
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Master your Time")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont("IBM Plex Sans", 11)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #71717A;") 
        header_layout.addWidget(subtitle_label)
        
        layout.addLayout(header_layout)
        layout.addSpacing(20)
        
        # Email field
        email_layout = QVBoxLayout()
        email_layout.setSpacing(8)
        email_layout.setContentsMargins(0, 0, 0, 0)
        
        email_label = QLabel("Email")
        email_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        email_layout.addWidget(email_label)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        self.email_input.setFont(QFont("IBM Plex Sans", 10))
        self.email_input.setFixedHeight(36)  # Tamaño original
        self.email_input.returnPressed.connect(self._on_login)
        self.email_input.textChanged.connect(self._validate_email)
        email_layout.addWidget(self.email_input)
        
        # Error label (más sutil)
        self.email_error = QLabel("")
        self.email_error.setFont(QFont("IBM Plex Sans", 9))
        self.email_error.setStyleSheet("color: #EF4444;")
        self.email_error.setVisible(False)
        self.email_error.setWordWrap(True)
        email_layout.addWidget(self.email_error)
        
        layout.addLayout(email_layout)
        
        # Password field
        pass_layout = QVBoxLayout()
        pass_layout.setSpacing(8)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        
        password_label = QLabel("Password")
        password_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
        pass_layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFont(QFont("IBM Plex Sans", 10))
        self.password_input.setFixedHeight(36)  # Tamaño original
        self.password_input.returnPressed.connect(self._on_login)
        self.password_input.textChanged.connect(self._validate_password)
        pass_layout.addWidget(self.password_input)
        
        # Error label (más sutil)
        self.password_error = QLabel("")
        self.password_error.setFont(QFont("IBM Plex Sans", 9))
        self.password_error.setStyleSheet("color: #EF4444;")
        self.password_error.setVisible(False)
        self.password_error.setWordWrap(True)
        pass_layout.addWidget(self.password_error)
        
        layout.addLayout(pass_layout)
        
        # Checkbox "Remember me"
        self.remember_checkbox = QCheckBox("Remember me for 7 days")
        self.remember_checkbox.setFont(QFont("IBM Plex Sans", 10))
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            }
        """)
        layout.addWidget(self.remember_checkbox)
        
        layout.addSpacing(16)
        
        # Login button (sin CustomButton para consistencia)
        self.login_button = QPushButton("Sign In")
        self.login_button.setFont(QFont("IBM Plex Sans", 11, QFont.Weight.Medium))
        self.login_button.setFixedHeight(36)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._on_login)
        layout.addWidget(self.login_button)
        
        layout.addStretch()
    
    def _apply_styles(self):
        """Aplica estilos CSS a la interfaz"""
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
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
                font-size: 14px;
                color: #09090B;
            }
            
            QLineEdit:focus {
                border: 1px solid #18181B;
                outline: none;
            }
            
            QLineEdit::placeholder {
                color: #A1A1AA;
            }
            
            QPushButton {
                background-color: #18181B;
                color: #FAFAFA;
                border: 1px solid #18181B;
                border-radius: 6px;
                padding: 4px 16px;
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
                font-weight: 500;
                font-size: 14px;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #27272A;
                border: 1px solid #27272A;
            }
            
            QPushButton:pressed {
                background-color: #09090B;
                border: 1px solid #09090B;
            }
            
            QPushButton:disabled {
                background-color: #E4E4E7;
                border: 1px solid #E4E4E7;
                color: #A1A1AA;
            }
            
            QLabel {
                color: #09090B;
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            }
        """)
    
    def _validate_email(self, text: str):
        """Valida el email en tiempo real."""
        if not text:
            self.email_error.setVisible(False)
            return
        
        if "@" not in text or "." not in text:
            self.email_error.setText("Please enter a valid email address")
            self.email_error.setVisible(True)
        else:
            self.email_error.setVisible(False)
    
    def _validate_password(self, text: str):
        """Valida la contraseña en tiempo real."""
        if not text:
            self.password_error.setVisible(False)
            return
        else:
            self.password_error.setVisible(False)
    
    def _on_login(self):
        """Maneja el evento de login"""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        # Validación inline
        has_error = False
        
        if not email:
            self.email_error.setText("Email is required")
            self.email_error.setVisible(True)
            has_error = True
        elif "@" not in email or "." not in email:
            self.email_error.setText("Please enter a valid email address")
            self.email_error.setVisible(True)
            has_error = True
        
        if not password:
            self.password_error.setText("Password is required")
            self.password_error.setVisible(True)
            has_error = True
        
            return
        
        # Deshabilitar botón
        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in...")
        
        # Ejecutar autenticación en thread separado
        self._login_worker = LoginWorker(email, password)
        self._login_worker.success.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._login_worker.start()
    

    
    def _on_login_success(self, supabase: Client, user_info: Dict):
        """Callback cuando el login es exitoso"""
        try:
            # Descargar configuración cifrada
            self.config = config_manager.fetch_config_from_db(supabase)
            
            # Validate config
            if not config_manager.validate_config(self.config):
                raise Exception("Incomplete configuration in database")
            
            # Guardar referencias
            self.supabase_client = supabase
            self.user_info = user_info
            
            # Guardar sesión si "Recordarme" está marcado
            if self.remember_checkbox.isChecked():
                session_manager.save_session(supabase, user_info, self.config)
            
            # Cerrar diálogo con éxito
            self.accept()
        
        except Exception as e:
            self._on_login_error(f"Error loading configuration: {str(e)}")
    
    def _on_login_error(self, error_message: str):
        """Callback cuando hay error en el login"""
        # Re-habilitar botón
        self.login_button.setEnabled(True)
        self.login_button.setText("Sign In")
        
        # Mostrar error
        show_message(
            self,
            "Authentication Error",
            error_message,
            QMessageBox.Icon.Critical
        )
    
    def closeEvent(self, event):
        """Maneja el cierre del diálogo"""
        # Si se cierra sin autenticar, limpiar y rechazar
        if not self.supabase_client:
            config_manager.clear_cache()
            self.reject()
        event.accept()
