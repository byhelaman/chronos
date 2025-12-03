"""
Chronos - UI Components
Biblioteca de componentes reutilizables para interfaces consistentes
"""

from PyQt6.QtWidgets import (
    QPushButton, QLineEdit, QLabel, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy, QToolButton, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from theme_manager import theme


class CustomButton(QPushButton):
    """Botón personalizado con variantes de estilo."""
    
    def __init__(self, text: str = "", variant: str = "primary", icon: QIcon = None, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(theme.button_style(variant))
        self.setFont(theme.get_qfont("BASE", 500))


class CustomInput(QLineEdit):
    """Input personalizado con estados de validación."""
    
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self._state = "default"  # default, success, error
        self._update_style()
        self.setFont(theme.get_qfont("BASE"))
    
    def set_state(self, state: str, message: str = ""):
        """Establece el estado del input (default, success, error)."""
        self._state = state
        self._update_style()
        
        # Aquí podrías añadir un tooltip o label con el mensaje
        if message:
            self.setToolTip(message)
    
    def _update_style(self):
        """Actualiza el estilo según el estado."""
        base_style = theme.input_style()
        
        if self._state == "error":
            base_style += f"""
                QLineEdit {{
                    border-color: {theme.COLORS['ERROR']};
                }}
            """
        elif self._state == "success":
            base_style += f"""
                QLineEdit {{
                    border-color: {theme.COLORS['SUCCESS']};
                }}
            """
        
        self.setStyleSheet(base_style)


class SearchBar(QWidget):
    """Barra de búsqueda con icono y botón de limpiar."""
    
    textChanged = pyqtSignal(str)
    
    def __init__(self, placeholder: str = "Search...", parent=None):
        super().__init__(parent)
        self._setup_ui(placeholder)
    
    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Container con border
        container = QFrame()
        container.setObjectName("searchContainer")
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(8)
        
        # Icono de búsqueda
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {theme.COLORS['TEXT_SECONDARY']};")
        container_layout.addWidget(search_icon)
        
        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFrame(False)
        self.input.setFont(theme.get_qfont("BASE"))
        self.input.textChanged.connect(self.textChanged.emit)
        self.input.textChanged.connect(self._on_text_changed)
        container_layout.addWidget(self.input)
        
        # Botón clear
        self.clear_btn = QToolButton()
        self.clear_btn.setText("×")
        self.clear_btn.setFont(theme.get_qfont("LG", 600))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setVisible(False)
        self.clear_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                color: {theme.COLORS['TEXT_SECONDARY']};
                padding: 0px;
                width: 20px;
                height: 20px;
            }}
            QToolButton:hover {{
                color: {theme.COLORS['TEXT_PRIMARY']};
                background-color: {theme.COLORS['SURFACE_SECONDARY']};
                border-radius: 10px;
            }}
        """)
        container_layout.addWidget(self.clear_btn)
        
        # Estilo del container
        container.setStyleSheet(f"""
            #searchContainer {{
                background-color: {theme.COLORS['SURFACE']};
                border: 1px solid {theme.COLORS['BORDER']};
                border-radius: {theme.RADIUS['MD']};
            }}
            #searchContainer:focus-within {{
                border-color: {theme.COLORS['BORDER_FOCUS']};
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                color: {theme.COLORS['TEXT_PRIMARY']};
            }}
            QLineEdit::placeholder {{
                color: {theme.COLORS['TEXT_TERTIARY']};
            }}
        """)
        
        layout.addWidget(container)
    
    def _on_text_changed(self, text: str):
        """Muestra/oculta el botón clear según el contenido."""
        self.clear_btn.setVisible(bool(text))
    
    def clear(self):
        """Limpia el input."""
        self.input.clear()
    
    def text(self) -> str:
        """Obtiene el texto del input."""
        return self.input.text()


class FilterChip(QWidget):
    """Chip para mostrar filtros activos con botón de cerrar."""
    
    closed = pyqtSignal()
    
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._setup_ui(label)
    
    def _setup_ui(self, label: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        
        # Label
        lbl = QLabel(label)
        lbl.setFont(theme.get_qfont("SM", 500))
        lbl.setStyleSheet(f"color: {theme.COLORS['TEXT_PRIMARY']};")
        layout.addWidget(lbl)
        
        # Botón cerrar
        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setFont(theme.get_qfont("BASE", 600))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.closed.emit)
        close_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                color: {theme.COLORS['TEXT_SECONDARY']};
                padding: 0px;
                width: 16px;
                height: 16px;
            }}
            QToolButton:hover {{
                color: {theme.COLORS['TEXT_PRIMARY']};
            }}
        """)
        layout.addWidget(close_btn)
        
        # Estilo del chip
        self.setStyleSheet(f"""
            FilterChip {{
                background-color: {theme.COLORS['ACCENT']};
                border: 1px solid {theme.COLORS['BORDER']};
                border-radius: {theme.RADIUS['FULL']};
            }}
        """)


class Badge(QLabel):
    """Badge para mostrar contadores o estados."""
    
    def __init__(self, text: str = "", variant: str = "default", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._update_style()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(theme.get_qfont("XS", 600))
        
        # Tamaño mínimo
        self.setMinimumSize(20, 20)
    
    def _update_style(self):
        """Actualiza el estilo según la variante."""
        bg_color = theme.COLORS['SURFACE_SECONDARY']
        text_color = theme.COLORS['TEXT_PRIMARY']
        
        if self.variant == "success":
            bg_color = theme.COLORS['SUCCESS_BG']
            text_color = theme.COLORS['SUCCESS']
        elif self.variant == "error":
            bg_color = theme.COLORS['ERROR_BG']
            text_color = theme.COLORS['ERROR']
        elif self.variant == "warning":
            bg_color = theme.COLORS['WARNING_BG']
            text_color = theme.COLORS['WARNING']
        elif self.variant == "info":
            bg_color = theme.COLORS['INFO_BG']
            text_color = theme.COLORS['INFO']
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 10px;
                padding: 2px 8px;
            }}
        """)


class Card(QFrame):
    """Card container con elevación y bordes redondeados."""
    
    def __init__(self, parent=None, elevated: bool = False):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        # Estilo base
        self.setStyleSheet(f"""
            Card {{
                background-color: {theme.COLORS['SURFACE']};
                border: 1px solid {theme.COLORS['BORDER']};
                border-radius: {theme.RADIUS['LG']};
            }}
        """)
        
        # Añadir sombra si está elevado
        if elevated:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 30))
            self.setGraphicsEffect(shadow)


class LoadingSpinner(QWidget):
    """Indicador de carga animado."""
    
    def __init__(self, size: int = 32, parent=None):
        super().__init__(parent)
        self.size = size
        self.angle = 0
        self.setFixedSize(size, size)
        
        # Timer para animación
        self.timer = QTimer()
        self.timer.timeout.connect(self._rotate)
        self.timer.start(50)  # 20 FPS
    
    def _rotate(self):
        """Rota el spinner."""
        self.angle = (self.angle + 30) % 360
        self.update()
    
    def paintEvent(self, event):
        """Dibuja el spinner."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Configurar pen
        pen = QPen(QColor(theme.COLORS['PRIMARY']))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Dibujar arco
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, self.angle * 16, 120 * 16)
    
    def stop(self):
        """Detiene la animación."""
        self.timer.stop()
    
    def start(self):
        """Inicia la animación."""
        self.timer.start(50)


class EmptyState(QWidget):
    """Widget para mostrar estado vacío con mensaje."""
    
    def __init__(self, title: str, description: str = "", icon: str = "📭", parent=None):
        super().__init__(parent)
        self._setup_ui(title, description, icon)
    
    def _setup_ui(self, title: str, description: str, icon: str):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(theme.SPACING['MD'])
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Icono
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(theme.get_qfont("3XL"))
        icon_label.setStyleSheet(f"color: {theme.COLORS['TEXT_TERTIARY']};")
        layout.addWidget(icon_label)
        
        # Título
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(theme.get_qfont("LG", 600))
        title_label.setStyleSheet(f"color: {theme.COLORS['TEXT_PRIMARY']};")
        layout.addWidget(title_label)
        
        # Descripción
        if description:
            desc_label = QLabel(description)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            desc_label.setFont(theme.get_qfont("SM"))
            desc_label.setStyleSheet(f"color: {theme.COLORS['TEXT_SECONDARY']};")
            layout.addWidget(desc_label)


class ToastNotification(QWidget):
    """Notificación toast temporal."""
    
    def __init__(self, message: str, variant: str = "info", duration: int = 3000, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._setup_ui(message, variant)
        
        # Auto-cerrar después de duration
        QTimer.singleShot(duration, self._fade_out)
    
    def _setup_ui(self, message: str, variant: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Icono según variante
        icons = {
            "success": "✓",
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ"
        }
        
        icon_label = QLabel(icons.get(variant, "ℹ"))
        icon_label.setFont(theme.get_qfont("LG", 600))
        layout.addWidget(icon_label)
        
        # Mensaje
        msg_label = QLabel(message)
        msg_label.setFont(theme.get_qfont("SM"))
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # Estilo según variante
        colors = {
            "success": (theme.COLORS['SUCCESS_BG'], theme.COLORS['SUCCESS'], theme.COLORS['SUCCESS']),
            "error": (theme.COLORS['ERROR_BG'], theme.COLORS['ERROR'], theme.COLORS['ERROR']),
            "warning": (theme.COLORS['WARNING_BG'], theme.COLORS['WARNING'], theme.COLORS['WARNING']),
            "info": (theme.COLORS['INFO_BG'], theme.COLORS['INFO'], theme.COLORS['INFO'])
        }
        
        bg, border, text = colors.get(variant, colors["info"])
        
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: {theme.RADIUS['LG']};
            }}
            QLabel {{
                color: {text};
            }}
        """)
        
        # Sombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)
    
    def _fade_out(self):
        """Animación de fade out antes de cerrar."""
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(1.0)
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.opacity_anim.finished.connect(self.close)
        self.opacity_anim.start()
    
    @staticmethod
    def show_toast(message: str, variant: str = "info", duration: int = 3000, parent=None):
        """Método estático para mostrar un toast rápidamente."""
        toast = ToastNotification(message, variant, duration, parent)
        
        # Posicionar en bottom-right de la pantalla o del parent
        if parent:
            parent_geometry = parent.geometry()
            x = parent_geometry.right() - toast.width() - 20
            y = parent_geometry.bottom() - toast.height() - 20
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = screen.width() - toast.sizeHint().width() - 20
            y = screen.height() - toast.sizeHint().height() - 80
        
        toast.move(x, y)
        toast.show()
        
        return toast
