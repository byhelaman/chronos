"""
Chronos - UI Delegates
Custom delegates for table styling and interaction.
"""

from PyQt6.QtWidgets import (
    QStyledItemDelegate, QHeaderView, QLineEdit, QStyle, QStyleOptionButton
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtCore import Qt, QModelIndex, QRect, pyqtSignal

from theme_manager import theme


class RowHoverDelegate(QStyledItemDelegate):
    """Delegate para resaltar la fila completa al pasar el mouse."""
    
    def __init__(self, parent=None, hover_color=None):
        super().__init__(parent)
        self.hover_color = QColor(hover_color or theme.colors.surface_secondary)
        self.hover_row = -1

    def paint(self, painter: QPainter, option, index: QModelIndex):
        if index.row() == self.hover_row:
            painter.save()
            painter.fillRect(option.rect, self.hover_color)
            painter.restore()
        super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        """Crea un editor de solo lectura para permitir copiar texto."""
        # No permitir edición en columna de checkbox (0)
        if index.column() == 0:
            return None
            
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        # Estilo del editor
        editor.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {theme.colors.border};
                border-radius: 4px;
                background-color: {theme.colors.surface}; 
                color: {theme.colors.text_primary};
                selection-background-color: {theme.colors.primary};
                selection-color: {theme.colors.primary_foreground};
                padding: 0 4px;
            }}
        """)
        return editor

    def setEditorData(self, editor, index):
        """Establece los datos en el editor y su alineación."""
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setText(str(text) if text else "")
        
        # Sincronizar alineación
        alignment = index.model().data(index, Qt.ItemDataRole.TextAlignmentRole)
        if alignment:
            horizontal_align = alignment & Qt.AlignmentFlag.AlignHorizontal_Mask
            editor.setAlignment(Qt.AlignmentFlag(horizontal_align))

    def updateEditorGeometry(self, editor, option, index):
        """Ajusta el tamaño del editor al contenido del texto (fit-content)."""
        text = str(index.model().data(index, Qt.ItemDataRole.DisplayRole) or "")
        
        # Calcular ancho necesario
        fm = option.fontMetrics
        text_width = fm.horizontalAdvance(text)
        required_width = text_width + 16  # Padding
        final_width = min(required_width, option.rect.width())
        
        # Crear el rectángulo final
        editor_rect = QRect(option.rect)
        editor_rect.setWidth(final_width)
        
        # Ajustar altura a 24px y centrar verticalmente
        target_height = 24
        vertical_diff = (option.rect.height() - target_height) // 2
        editor_rect.setHeight(target_height)
        editor_rect.moveTop(option.rect.top() + vertical_diff)
        
        # Ajustar alineación horizontal
        alignment = index.model().data(index, Qt.ItemDataRole.TextAlignmentRole)
        if alignment is None:
            alignment = Qt.AlignmentFlag.AlignLeft
            
        if alignment & Qt.AlignmentFlag.AlignHCenter:
            editor_rect.moveCenter(option.rect.center())
            editor_rect.moveTop(option.rect.top() + vertical_diff)
        elif alignment & Qt.AlignmentFlag.AlignRight:
            editor_rect.moveRight(option.rect.right() - 4)
        else:
            editor_rect.moveLeft(option.rect.left() + 4)
            
        editor.setGeometry(editor_rect)

    def setModelData(self, editor, model, index):
        """No hace nada porque es solo lectura."""
        pass


class CheckBoxHeader(QHeaderView):
    """Header personalizado con un checkbox en la primera columna."""
    
    checkBoxClicked = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.isOn = False

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == 0:
            # Pintar fondo
            painter.fillRect(rect, QColor(theme.colors.surface_secondary))
            
            # Dibujar border bottom
            painter.setPen(QPen(QColor(theme.colors.border), 1))
            painter.drawLine(rect.x(), rect.bottom(), rect.right(), rect.bottom())
            
            # Dibujar checkbox
            option = QStyleOptionButton()
            option.rect = QRect(rect.x() + 15, rect.y() + 12, 20, 20)
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            
            if self.isOn:
                option.state |= QStyle.StateFlag.State_On
            else:
                option.state |= QStyle.StateFlag.State_Off
            
            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            logicalIndex = self.logicalIndexAt(event.position().toPoint())
            
            if logicalIndex == 0:
                self.isOn = not self.isOn
                self.checkBoxClicked.emit(self.isOn)
                self.viewport().update()
                return  # No llamar a super() para evitar sort

        super().mousePressEvent(event)

    def setChecked(self, checked: bool):
        """Establece el estado del checkbox."""
        self.isOn = checked
        self.viewport().update()

    def isChecked(self) -> bool:
        """Retorna el estado del checkbox."""
        return self.isOn


__all__ = ["RowHoverDelegate", "CheckBoxHeader"]
