"""
Chronos - Meeting Search Dialog
Dialog for searching and filtering Zoom meetings.
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QAbstractItemView, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from theme_manager import theme
from app.ui.delegates import RowHoverDelegate
from app.workers import MeetingSearchWorker


APP_NAME = "Chronos"


def custom_message_box(parent, title, text, icon, buttons):
    """Helper para mostrar alertas con estilos personalizados."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    return msg.exec()


class MeetingSearchDialog(QDialog):
    """Diálogo para buscar y filtrar reuniones."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} | Search Meetings")
        self.setModal(True)
        self.setFixedSize(1000, 600)
        
        # Use theme colors
        self.COLORS = {
            "BACKGROUND": theme.colors.background,
            "SURFACE": theme.colors.surface,
            "SURFACE_SECONDARY": theme.colors.surface_secondary,
            "BORDER": theme.colors.border,
            "TEXT_PRIMARY": theme.colors.text_primary,
            "TEXT_SECONDARY": theme.colors.text_secondary,
            "PRIMARY": theme.colors.primary,
            "PRIMARY_FOREGROUND": theme.colors.primary_foreground,
        }

        self.setStyleSheet(f"""
            QDialog {{ background-color: {self.COLORS['BACKGROUND']}; }}
            QLabel {{ font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif; border-radius: 6px; padding: 8px 16px; font-weight: 500; font-size: 14px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("Search Meetings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Find Zoom meetings by program or instructor.")
        desc.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']};")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addLayout(header_layout)
        
        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Program/Topic...")
        self.search_input.setMinimumWidth(250)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif; border: 1px solid {self.COLORS['BORDER']}; border-radius: 6px; padding: 8px 12px; background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid #18181B; }}
        """)
        self.search_input.textChanged.connect(self.filter_table)
        
        self.instructor_input = QLineEdit()
        self.instructor_input.setPlaceholderText("Filter by Instructor...")
        self.instructor_input.setMinimumWidth(200)
        self.instructor_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif; border: 1px solid {self.COLORS['BORDER']}; border-radius: 6px; padding: 8px 12px; background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid #18181B; }}
        """)
        self.instructor_input.textChanged.connect(self.filter_table)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; border: 1px solid {self.COLORS['BORDER']}; }}
            QPushButton:hover {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; }}
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.instructor_input)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: {self.COLORS['SURFACE_SECONDARY']}; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {self.COLORS['PRIMARY']}; border-radius: 2px; }}
        """)
        layout.addWidget(self.progress_bar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Meeting ID", "Topic", "Host", "Created At"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Table Styles
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color: {self.COLORS['SURFACE']}; border: 1px solid {self.COLORS['BORDER']}; border-radius: 8px; outline: none; }}
            QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {self.COLORS['BORDER']}; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QTableWidget::item:selected {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QHeaderView::section {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; color: {self.COLORS['TEXT_SECONDARY']}; padding: 12px; border: none; border-bottom: 1px solid {self.COLORS['BORDER']}; font-weight: 600; }}
            QScrollBar:vertical {{ background-color: {self.COLORS['SURFACE']}; border: none; width: 8px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{ background: {self.COLORS['BORDER']};border-radius: 4px; min-height: 40px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        
        # Column Widths
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 360)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 150)
        
        # Hover Delegate
        self.table.setMouseTracking(True)
        self.hover_delegate = RowHoverDelegate(self.table)
        self.table.setItemDelegate(self.hover_delegate)
        self.table.cellEntered.connect(self.on_cell_entered)
        self.table.cellClicked.connect(self.on_cell_clicked)
        
        layout.addWidget(self.table)
        
        # Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['PRIMARY']}; color: {self.COLORS['PRIMARY_FOREGROUND']}; border: 1px solid {self.COLORS['PRIMARY']}; }}
            QPushButton:hover {{ background-color: #27272A; }}
        """)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        # Data
        self.all_meetings = []
        
        # Load Data on Open
        QTimer.singleShot(100, self.load_data)

    def on_cell_entered(self, row, column):
        self.hover_delegate.hover_row = row
        if column == 0:
            self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.table.setCursor(Qt.CursorShape.ArrowCursor)
        self.table.viewport().update()

    def on_cell_clicked(self, row, column):
        if column == 0:
            item = self.table.item(row, column)
            if item:
                mid = item.text()
                url = f"https://zoom.us/meeting/{mid}"
                QDesktopServices.openUrl(QUrl(url))

    def load_data(self):
        self.table.setRowCount(0)
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = MeetingSearchWorker()
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.start()
        
    def update_progress(self, msg):
        self.setWindowTitle(f"{APP_NAME} | Search Meetings - {msg}")

    def on_data_loaded(self, meetings, errors):
        self.refresh_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.setWindowTitle(f"{APP_NAME} | Search Meetings")
        
        if errors:
            custom_message_box(
                self, "Error", f"Error loading data: {errors[0]}",
                QMessageBox.Icon.Critical, QMessageBox.StandardButton.Ok
            )
            return
            
        self.all_meetings = meetings
        self.populate_table(meetings)

    def populate_table(self, meetings):
        self.table.setRowCount(len(meetings))
        self.table.setSortingEnabled(False)
        
        for i, m in enumerate(meetings):
            # ID
            id_item = QTableWidgetItem(str(m.get("meeting_id")))
            id_item.setForeground(QColor("#2563EB"))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = id_item.font()
            font.setUnderline(True)
            id_item.setFont(font)
            self.table.setItem(i, 0, id_item)
            
            # Topic
            self.table.setItem(i, 1, QTableWidgetItem(str(m.get("topic", ""))))
            
            # Host
            host_item = QTableWidgetItem(str(m.get("host_name", "")))
            host_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, host_item)
            
            # Created At
            created_at = m.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
            created_at_item = QTableWidgetItem(created_at)
            created_at_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, created_at_item)
            
        self.table.setSortingEnabled(True)

    def filter_table(self):
        search_text = self.search_input.text().lower().strip()
        instructor_filter = self.instructor_input.text().lower().strip()
        
        filtered = []
        for m in self.all_meetings:
            host_name = str(m.get("host_name", "")).lower()
            if instructor_filter and instructor_filter not in host_name:
                continue
                
            topic = str(m.get("topic", "")).lower()
            mid = str(m.get("meeting_id", ""))
            
            if search_text and (search_text not in topic and search_text not in mid):
                continue
                
            filtered.append(m)
            
        self.populate_table(filtered)


__all__ = ["MeetingSearchDialog"]
