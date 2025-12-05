"""
Chronos - Link Creation Dialog
Dialog for creating Zoom links for a list of programs.
"""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QComboBox,
    QAbstractItemView, QFrame, QMessageBox, QStyle, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from theme_manager import theme
from app.workers import LinkCreationWorker
from app.services.auth_service import auth_service
from app.ui.delegates import RowHoverDelegate

APP_NAME = "Chronos"
logger = logging.getLogger(__name__)


def custom_message_box(parent, title, text, icon, buttons):
    """Helper para mostrar alertas con estilos personalizados en botones."""
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
    
    # Estilizar botones secundarios (No, Cancel, Close)
    secondary_buttons = [
        QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Cancel,
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
                        font-family: 'IBM Plex Sans', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #F4F4F5;
                    }
                    QPushButton:pressed {
                        background-color: #E4E4E7;
                    }
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
    
    # Estilizar botones primarios (Yes, Ok, Save, Open)
    primary_buttons = [
        QMessageBox.StandardButton.Yes,
        QMessageBox.StandardButton.Ok,
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.Open,
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
                        font-family: 'IBM Plex Sans', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #27272A;
                    }
                    QPushButton:pressed {
                        background-color: #09090B;
                    }
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

    return msg.exec()


class LinkCreationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} | Create Links")
        self.setModal(True)
        self.setFixedSize(900, 700)
        
        self.all_results = []
        
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
            QTextEdit {{
                font-family: 'IBM Plex Sans', sans-serif; 
                border: 1px solid {self.COLORS['BORDER']}; 
                border-radius: 6px; 
                padding: 8px; 
                background-color: {self.COLORS['SURFACE']}; 
                color: {self.COLORS['TEXT_PRIMARY']}; 
                font-size: 14px;
            }}
            QComboBox {{
                font-family: 'IBM Plex Sans', sans-serif; border: 1px solid {self.COLORS['BORDER']}; border-radius: 6px; padding: 4px 8px; background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; font-size: 14px;
            }}
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif; border-radius: 6px; padding: 8px 16px; font-weight: 500; font-size: 14px;
            }}
            /* Scrollbars for TextEdit */
            QScrollBar:vertical {{
                border: none; background: {self.COLORS['SURFACE']};
                width: 8px; margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLORS['BORDER']};
                min-height: 40px; border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Create Zoom Links")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {self.COLORS['TEXT_PRIMARY']};")
        header_layout.addWidget(title)
        layout.addLayout(header_layout)
        
        # Input Area
        input_layout = QVBoxLayout()
        
        # Input Header (Label + Status)
        input_header_layout = QHBoxLayout()
        input_label = QLabel("Paste Programs (one per line):")
        input_header_layout.addWidget(input_label)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #10B981; font-weight: 600; font-size: 14px;") # Emerald-500
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        input_header_layout.addWidget(self.status_label)
        
        input_layout.addLayout(input_header_layout)
        
        self.program_input = QTextEdit()
        self.program_input.setPlaceholderText("Paste list of programs here...")
        self.program_input.setMinimumHeight(150)
        input_layout.addWidget(self.program_input)
        layout.addLayout(input_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; background-color: {self.COLORS['SURFACE_SECONDARY']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS['PRIMARY']}; border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Status", "Program", "Meeting ID", "Link"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Allow multi-select
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setFixedHeight(45)
        
        # Configurar Hover Delegate (Igual que tabla principal)
        self.hover_delegate = RowHoverDelegate(self.table, self.COLORS['SURFACE_SECONDARY'])
        self.table.setItemDelegate(self.hover_delegate)
        self.table.setMouseTracking(True)
        self.table.cellEntered.connect(self.on_cell_entered)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.COLORS['BACKGROUND']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                outline: none;
                gridline-color: {self.COLORS['BORDER']};
            }}
            QHeaderView::section {{
                background-color: #F4F4F5;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                font-weight: 600;
                color: {self.COLORS['TEXT_SECONDARY']};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {self.COLORS['BORDER']};
            }}
            QTableWidget::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
        """)
        
        self.table.setColumnWidth(0, 120) # Status
        self.table.setColumnWidth(1, 350) # Program
        self.table.setColumnWidth(2, 120) # Meeting ID
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.table.cellClicked.connect(self.on_cell_clicked)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12) # Spacing 12px
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; border: 1px solid {self.COLORS['BORDER']}; }}
            QPushButton:hover {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; }}
        """)
        self.close_btn.clicked.connect(self.accept)
        
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; border: 1px solid {self.COLORS['BORDER']}; }}
            QPushButton:hover {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; }}
        """)
        self.verify_btn.clicked.connect(self.verify_links)
        
        self.create_btn = QPushButton("Create Links")
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.setEnabled(False) # Disabled until verified
        self.create_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['PRIMARY']}; color: {self.COLORS['PRIMARY_FOREGROUND']}; border: 1px solid {self.COLORS['PRIMARY']}; }}
            QPushButton:hover {{ background-color: #27272A; }}
            QPushButton:disabled {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; color: {self.COLORS['TEXT_SECONDARY']}; border: 1px solid {self.COLORS['BORDER']}; }}
        """)
        self.create_btn.clicked.connect(self.create_links)
        
        btn_layout.addWidget(self.close_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.verify_btn)
        btn_layout.addWidget(self.create_btn)
        layout.addLayout(btn_layout)

    def on_cell_entered(self, row, column):
        self.hover_delegate.hover_row = row
        self.table.viewport().update()

    def on_cell_clicked(self, row, column):
        pass

    def show_context_menu(self, position):
        """Muestra el menú contextual."""
        menu = QMenu(self)
        
        # Estilo del menú (copiado de app_legacy.py para consistencia)
        menu.setStyleSheet(f"""
            QMenu {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 12px;
                border-radius: 4px;
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QMenu::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
        """)
        
        # Get selected items
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()))
        
        if not selected_rows:
            return
            
        # Copy Rows
        if len(selected_rows) > 1:
            copy_rows_action = menu.addAction(f"Copy {len(selected_rows)} selected Rows")
            copy_rows_action.triggered.connect(self.copy_selected_rows)
            
            menu.addSeparator()
            
            deselect_action = menu.addAction("Deselect All")
            deselect_action.triggered.connect(self.table.clearSelection)
        else:
            copy_row_action = menu.addAction("Copy Row")
            copy_row_action.triggered.connect(lambda: self.copy_single_row(selected_rows[0]))
            
        menu.exec(self.table.viewport().mapToGlobal(position))

    def copy_selected_rows(self):
        """Copia las filas seleccionadas al portapapeles."""
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()))
        blocks = []
        for row in selected_rows:
            program_item = self.table.item(row, 1)
            program = program_item.text() if program_item else ""
            
            link_item = self.table.item(row, 3)
            link = link_item.text() if link_item else ""
            
            blocks.append(f"{program}\n{link}")
        
        QApplication.clipboard().setText("\n\n".join(blocks))
        
        # Show status instead of popup
        self.status_label.setText(f"✓ Copied {len(selected_rows)} rows")

    def copy_single_row(self, row):
        """Copia una sola fila."""
        program_item = self.table.item(row, 1)
        program = program_item.text() if program_item else ""
        
        link_item = self.table.item(row, 3)
        link = link_item.text() if link_item else ""
        
        QApplication.clipboard().setText(f"{program}\n{link}")
        
        # Show status instead of popup
        self.status_label.setText("✓ Copied 1 row")

    def verify_links(self):
        """Inicia el proceso de verificación."""
        text = self.program_input.toPlainText()
        programs = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not programs:
            custom_message_box(
                self, "Warning", "Please enter at least one program.",
                QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok
            )
            return
            
        self.verify_btn.setEnabled(False)
        self.create_btn.setEnabled(False)
        self.program_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.table.setRowCount(0)
        
        self.worker = LinkCreationWorker(programs, mode="verify")
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def create_links(self):
        """Inicia el proceso de creación/actualización para los items marcados."""
        # Get current table data with status
        items_to_process = []
        for i in range(self.table.rowCount()):
            status_item = self.table.item(i, 0)
            program_item = self.table.item(i, 1)
            meeting_id_item = self.table.item(i, 2)
            link_item = self.table.item(i, 3)
            
            if status_item and program_item:
                status_text = status_item.text().lower().replace(" ", "_")
                # Convert UI status to internal status
                if status_text == "to_create":
                    status_text = "ready"
                elif status_text == "to_update":
                    status_text = "to_update"
                else:
                    status_text = status_item.text().lower()
                
                items_to_process.append({
                    "program": program_item.text(),
                    "status": status_text,
                    "meeting_id": meeting_id_item.text() if meeting_id_item else "-",
                    "join_url": link_item.data(Qt.ItemDataRole.UserRole) if link_item else ""
                })
        
        # Check if there's anything to process
        actionable = [i for i in items_to_process if i["status"] in ["ready", "to_update"]]
        if not actionable:
            return

        self.verify_btn.setEnabled(False)
        self.create_btn.setEnabled(False)
        self.program_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = LinkCreationWorker(items_to_process, mode="create")
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def update_progress(self, msg):
        self.setWindowTitle(f"{APP_NAME} | {msg}")

    def on_finished(self, results, errors, mode):
        self.verify_btn.setEnabled(True)
        self.program_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.setWindowTitle(f"{APP_NAME} | Create Links")
        
        if mode == "verify":
            self.all_results = results
            self.populate_table(self.all_results)
            
            # Check if any ready to create or update
            ready_count = sum(1 for r in results if r["status"] == "ready")
            existing_count = sum(1 for r in results if r["status"] == "existing")
            
            if ready_count > 0 or existing_count > 0:
                self.create_btn.setEnabled(True)
                btn_text = []
                if ready_count > 0:
                    btn_text.append(f"Create ({ready_count})")
                self.create_btn.setText(" / ".join(btn_text) if btn_text else "Process")
            else:
                self.create_btn.setEnabled(False)
                self.create_btn.setText("Create Links")
                
        elif mode == "create":
            # Update all_results with new results
            self.all_results = results
            self.populate_table(self.all_results)
            self.create_btn.setEnabled(False)
            self.create_btn.setText("Create Links")
            
            created_count = sum(1 for r in results if r["status"] == "created")
            updated_count = sum(1 for r in results if r["status"] == "updated")
            
            if errors:
                custom_message_box(
                    self, "Completed with Errors", 
                    f"Process completed with {len(errors)} errors.\nCheck the table for details.",
                    QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok
                )
            else:
                msg_parts = []
                if created_count > 0:
                    msg_parts.append(f"Created {created_count} links")
                if updated_count > 0:
                    msg_parts.append(f"Updated {updated_count} meetings")
                custom_message_box(
                    self, "Success", 
                    ".\n".join(msg_parts) + ".",
                    QMessageBox.Icon.Information, QMessageBox.StandardButton.Ok
                )

    def populate_table(self, results):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        
        for i, res in enumerate(results):
            # Status (Column 0)
            status = res["status"]
            status_item = QTableWidgetItem()
            
            # Map status to display text and color
            status_config = {
                "ready": ("To Create", "#16a34a"),      # Green
                "existing": ("Existing", "#71717a"),    # Gray
                "to_update": ("To Update", "#2563eb"),  # Blue
                "created": ("Created", "#16a34a"),      # Green
                "updated": ("Updated", "#2563eb"),      # Blue
                "error": ("Error", "#dc2626"),          # Red
            }
            
            display_text, color = status_config.get(status, (status.title(), "#71717a"))
            status_item.setText(display_text)
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Store original status for processing
            status_item.setData(Qt.ItemDataRole.UserRole, status)
            self.table.setItem(i, 0, status_item)

            # Program (Column 1)
            prog_item = QTableWidgetItem(res["program"])
            prog_item.setFlags(prog_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, prog_item)
            
            # Meeting ID (Column 2) - Clickable link
            meeting_id = res["meeting_id"]
            id_item = QTableWidgetItem(meeting_id)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if meeting_id and meeting_id != "-":
                id_item.setForeground(QColor("#2563EB"))
                font = id_item.font()
                font.setUnderline(True)
                id_item.setFont(font)
                # Store zoom meeting URL for click handling
                id_item.setData(Qt.ItemDataRole.UserRole, f"https://zoom.us/meeting/{meeting_id}")
            self.table.setItem(i, 2, id_item)
            
            # Link (Column 3)
            link = res.get("join_url", "")
            link_item = QTableWidgetItem(link)
            if link and link != "-":
                link_item.setForeground(QColor("#2563EB"))
                font = link_item.font()
                font.setUnderline(True)
                link_item.setFont(font)
                link_item.setData(Qt.ItemDataRole.UserRole, link)
            
            self.table.setItem(i, 3, link_item)
            
        self.table.setSortingEnabled(True)
        self._update_create_button()
    
    def _update_create_button(self):
        """Update create button text based on current table state."""
        ready_count = 0
        update_count = 0
        
        for i in range(self.table.rowCount()):
            status_item = self.table.item(i, 0)
            if status_item:
                status = status_item.data(Qt.ItemDataRole.UserRole)
                if status == "ready":
                    ready_count += 1
                elif status == "to_update":
                    update_count += 1
        
        if ready_count > 0 or update_count > 0:
            self.create_btn.setEnabled(True)
            parts = []
            if ready_count > 0:
                parts.append(f"Create ({ready_count})")
            if update_count > 0:
                parts.append(f"Update ({update_count})")
            self.create_btn.setText(" / ".join(parts))
        else:
            self.create_btn.setEnabled(False)
            self.create_btn.setText("Create Links")

    def on_cell_clicked(self, row, column):
        if column == 0:  # Status column - toggle
            item = self.table.item(row, column)
            if item:
                current_status = item.data(Qt.ItemDataRole.UserRole)
                # Toggle between existing <-> to_update
                if current_status == "existing":
                    item.setText("To Update")
                    item.setForeground(QColor("#2563eb"))
                    item.setData(Qt.ItemDataRole.UserRole, "to_update")
                    self._update_create_button()
                elif current_status == "to_update":
                    item.setText("Existing")
                    item.setForeground(QColor("#71717a"))
                    item.setData(Qt.ItemDataRole.UserRole, "existing")
                    self._update_create_button()
                    
        elif column in [2, 3]:  # Meeting ID or Link column
            item = self.table.item(row, column)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    QDesktopServices.openUrl(QUrl(url))
