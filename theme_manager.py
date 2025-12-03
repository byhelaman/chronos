"""
Chronos - Theme Manager
Sistema centralizado de temas y estilos para toda la aplicación
"""

from typing import Dict, Any
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication


class ThemeManager:
    """Gestor centralizado de temas para mantener consistencia visual."""
    
    # ============================================================================
    # PALETA DE COLORES
    # ============================================================================
    
    COLORS = {
        # Base
        "BACKGROUND": "#FFFFFF",
        "SURFACE": "#FFFFFF",
        "SURFACE_SECONDARY": "#F4F4F5",
        "SURFACE_HOVER": "#FAFAFA",
        
        # Borders
        "BORDER": "#E4E4E7",
        "BORDER_STRONG": "#D4D4D8",
        "BORDER_FOCUS": "#18181B",
        
        # Text
        "TEXT_PRIMARY": "#09090B",
        "TEXT_SECONDARY": "#71717A",
        "TEXT_TERTIARY": "#A1A1AA",
        "TEXT_DISABLED": "#D4D4D8",
        
        # Brand/Primary
        "PRIMARY": "#18181B",
        "PRIMARY_HOVER": "#27272A",
        "PRIMARY_PRESSED": "#09090B",
        "PRIMARY_FOREGROUND": "#FAFAFA",
        
        # Semantic colors
        "SUCCESS": "#22C55E",
        "SUCCESS_BG": "#F0FDF4",
        "WARNING": "#F59E0B",
        "WARNING_BG": "#FFFBEB",
        "ERROR": "#EF4444",
        "ERROR_BG": "#FEF2F2",
        "INFO": "#3B82F6",
        "INFO_BG": "#EFF6FF",
        
        # Accent
        "ACCENT": "#F4F4F5",
        "ACCENT_FOREGROUND": "#18181B",
        
        # Destructive
        "DESTRUCTIVE": "#EF4444",
        "DESTRUCTIVE_HOVER": "#DC2626",
        "DESTRUCTIVE_FOREGROUND": "#FFFFFF",
        
        # Overlays
        "OVERLAY": "rgba(0, 0, 0, 0.5)",
        "GLASS_BG": "rgba(255, 255, 255, 0.8)",
    }
    
    # ============================================================================
    # TIPOGRAFÍA
    # ============================================================================
    
    FONTS = {
        "FAMILY": "IBM Plex Sans",
        "FAMILY_FALLBACK": "'IBM Plex Sans', 'Segoe UI', sans-serif",
        "SIZE_XS": "11px",
        "SIZE_SM": "12px",
        "SIZE_BASE": "14px",
        "SIZE_LG": "16px",
        "SIZE_XL": "18px",
        "SIZE_2XL": "20px",
        "SIZE_3XL": "24px",
    }
    
    # ============================================================================
    # SPACING (Sistema de 4px)
    # ============================================================================
    
    SPACING = {
        "XS": 4,
        "SM": 8,
        "MD": 12,
        "LG": 16,
        "XL": 20,
        "2XL": 24,
        "3XL": 32,
        "4XL": 40,
    }
    
    # ============================================================================
    # BORDER RADIUS
    # ============================================================================
    
    RADIUS = {
        "SM": "4px",
        "MD": "6px",
        "LG": "8px",
        "XL": "12px",
        "FULL": "9999px",
    }
    
    # ============================================================================
    # SHADOWS (CSS)
    # ============================================================================
    
    SHADOWS = {
        "SM": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        "MD": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        "LG": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
        "XL": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
    }
    
    # ============================================================================
    # TRANSICIONES
    # ============================================================================
    
    TRANSITIONS = {
        "FAST": "150ms",
        "BASE": "200ms",
        "SLOW": "300ms",
    }
    
    # ============================================================================
    # HELPERS PARA GENERAR ESTILOS
    # ============================================================================
    
    @classmethod
    def button_style(cls, variant: str = "primary") -> str:
        """Genera estilos para botones según variante."""
        base_style = f"""
            QPushButton {{
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                font-size: {cls.FONTS['SIZE_BASE']};
                font-weight: 500;
                border-radius: {cls.RADIUS['MD']};
                padding: 8px 16px;
                border: 1px solid;
            }}
        """
        
        if variant == "primary":
            return base_style + f"""
                QPushButton {{
                    background-color: {cls.COLORS['PRIMARY']};
                    color: {cls.COLORS['PRIMARY_FOREGROUND']};
                    border-color: {cls.COLORS['PRIMARY']};
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['PRIMARY_HOVER']};
                    border-color: {cls.COLORS['PRIMARY_HOVER']};
                }}
                QPushButton:pressed {{
                    background-color: {cls.COLORS['PRIMARY_PRESSED']};
                    border-color: {cls.COLORS['PRIMARY_PRESSED']};
                }}
                QPushButton:disabled {{
                    background-color: {cls.COLORS['SURFACE_SECONDARY']};
                    color: {cls.COLORS['TEXT_DISABLED']};
                    border-color: {cls.COLORS['BORDER']};
                }}
            """
        elif variant == "secondary":
            return base_style + f"""
                QPushButton {{
                    background-color: {cls.COLORS['SURFACE']};
                    color: {cls.COLORS['TEXT_PRIMARY']};
                    border-color: {cls.COLORS['BORDER']};
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['SURFACE_SECONDARY']};
                    border-color: {cls.COLORS['BORDER_STRONG']};
                }}
                QPushButton:pressed {{
                    background-color: {cls.COLORS['ACCENT']};
                }}
                QPushButton:disabled {{
                    background-color: {cls.COLORS['SURFACE']};
                    color: {cls.COLORS['TEXT_DISABLED']};
                    border-color: {cls.COLORS['BORDER']};
                }}
            """
        elif variant == "ghost":
            return base_style + f"""
                QPushButton {{
                    background-color: transparent;
                    color: {cls.COLORS['TEXT_PRIMARY']};
                    border-color: transparent;
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['SURFACE_SECONDARY']};
                }}
                QPushButton:pressed {{
                    background-color: {cls.COLORS['ACCENT']};
                }}
                QPushButton:disabled {{
                    color: {cls.COLORS['TEXT_DISABLED']};
                }}
            """
        elif variant == "destructive":
            return base_style + f"""
                QPushButton {{
                    background-color: {cls.COLORS['DESTRUCTIVE']};
                    color: {cls.COLORS['DESTRUCTIVE_FOREGROUND']};
                    border-color: {cls.COLORS['DESTRUCTIVE']};
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['DESTRUCTIVE_HOVER']};
                    border-color: {cls.COLORS['DESTRUCTIVE_HOVER']};
                }}
                QPushButton:pressed {{
                    background-color: #B91C1C;
                }}
                QPushButton:disabled {{
                    background-color: {cls.COLORS['SURFACE_SECONDARY']};
                    color: {cls.COLORS['TEXT_DISABLED']};
                    border-color: {cls.COLORS['BORDER']};
                }}
            """
        
        return base_style
    
    @classmethod
    def input_style(cls) -> str:
        """Genera estilos para inputs de texto."""
        return f"""
            QLineEdit {{
                background-color: {cls.COLORS['SURFACE']};
                border: 1px solid {cls.COLORS['BORDER']};
                border-radius: {cls.RADIUS['MD']};
                padding: 8px 12px;
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                font-size: {cls.FONTS['SIZE_BASE']};
                color: {cls.COLORS['TEXT_PRIMARY']};
            }}
            QLineEdit:focus {{
                border-color: {cls.COLORS['BORDER_FOCUS']};
                outline: none;
            }}
            QLineEdit:disabled {{
                background-color: {cls.COLORS['SURFACE_SECONDARY']};
                color: {cls.COLORS['TEXT_DISABLED']};
            }}
            QLineEdit::placeholder {{
                color: {cls.COLORS['TEXT_TERTIARY']};
            }}
        """
    
    @classmethod
    def combobox_style(cls) -> str:
        """Genera estilos para combobox."""
        return f"""
            QComboBox {{
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                border: 1px solid {cls.COLORS['BORDER']};
                border-radius: {cls.RADIUS['MD']};
                padding: 4px 8px;
                background-color: {cls.COLORS['SURFACE']};
                color: {cls.COLORS['TEXT_PRIMARY']};
                font-size: {cls.FONTS['SIZE_BASE']};
            }}
            QComboBox:hover {{
                border-color: {cls.COLORS['BORDER_FOCUS']};
            }}
            QComboBox:focus {{
                border-color: {cls.COLORS['BORDER_FOCUS']};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                background-color: {cls.COLORS['SURFACE']};
                border: 1px solid {cls.COLORS['BORDER']};
                border-radius: {cls.RADIUS['MD']};
                selection-background-color: {cls.COLORS['ACCENT']};
                selection-color: {cls.COLORS['TEXT_PRIMARY']};
                padding: 4px;
            }}
        """
    
    @classmethod
    def table_style(cls) -> str:
        """Genera estilos para tablas."""
        return f"""
            QTableWidget {{
                background-color: {cls.COLORS['SURFACE']};
                border: 1px solid {cls.COLORS['BORDER']};
                border-radius: {cls.RADIUS['LG']};
                gridline-color: transparent;
                outline: none;
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                font-size: {cls.FONTS['SIZE_BASE']};
            }}
            QTableWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {cls.COLORS['BORDER']};
                color: {cls.COLORS['TEXT_PRIMARY']};
            }}
            QTableWidget::item:selected {{
                background-color: {cls.COLORS['SURFACE_SECONDARY']};
                color: {cls.COLORS['TEXT_PRIMARY']};
            }}
            QHeaderView::section {{
                background-color: {cls.COLORS['SURFACE_SECONDARY']};
                color: {cls.COLORS['TEXT_SECONDARY']};
                padding: 12px;
                border: none;
                border-bottom: 1px solid {cls.COLORS['BORDER']};
                font-weight: 600;
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                font-size: {cls.FONTS['SIZE_BASE']};
            }}
            QTableWidget::corner {{
                background-color: {cls.COLORS['SURFACE']};
                border: none;
            }}
        """
    
    @classmethod
    def scrollbar_style(cls) -> str:
        """Genera estilos para scrollbars."""
        return f"""
            QScrollBar:vertical {{
                border: none;
                background: {cls.COLORS['SURFACE']};
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.COLORS['BORDER']};
                min-height: 40px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.COLORS['BORDER_STRONG']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {cls.COLORS['SURFACE']};
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {cls.COLORS['BORDER']};
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {cls.COLORS['BORDER_STRONG']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """
    
    @classmethod
    def progressbar_style(cls) -> str:
        """Genera estilos para progress bars."""
        return f"""
            QProgressBar {{
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                border: none;
                background-color: {cls.COLORS['SURFACE_SECONDARY']};
                border-radius: 2px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {cls.COLORS['PRIMARY']};
                border-radius: 2px;
            }}
        """
    
    @classmethod
    def messagebox_style(cls) -> str:
        """Genera estilos para message boxes."""
        return f"""
            QMessageBox {{
                background-color: {cls.COLORS['BACKGROUND']};
                min-width: 200px;
            }}
            QMessageBox QLabel {{
                color: {cls.COLORS['TEXT_PRIMARY']};
                font-family: {cls.FONTS['FAMILY_FALLBACK']};
                font-size: {cls.FONTS['SIZE_BASE']};
            }}
        """
    
    @classmethod
    def get_qfont(cls, size: str = "BASE", weight: int = 400) -> QFont:
        """Obtiene un QFont configurado según el tema."""
        font_size_map = {
            "XS": 11,
            "SM": 12,
            "BASE": 14,
            "LG": 16,
            "XL": 18,
            "2XL": 20,
            "3XL": 24,
        }
        
        font = QFont(cls.FONTS['FAMILY'], font_size_map.get(size, 14))
        
        # Mapear weight a QFont.Weight
        if weight >= 700:
            font.setWeight(QFont.Weight.Bold)
        elif weight >= 600:
            font.setWeight(QFont.Weight.DemiBold)
        elif weight >= 500:
            font.setWeight(QFont.Weight.Medium)
        else:
            font.setWeight(QFont.Weight.Normal)
            
        return font


# Instancia global del theme
theme = ThemeManager()
