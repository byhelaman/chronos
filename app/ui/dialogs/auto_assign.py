"""
Chronos - Auto Assign Dialog
Dialog for automatic meeting assignment based on schedule matching.
"""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QComboBox,
    QAbstractItemView, QFrame, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import QItemSelectionModel

from theme_manager import theme
from app.ui.delegates import RowHoverDelegate, CheckBoxHeader
from app.workers import AssignmentWorker, UpdateWorker


APP_NAME = "Chronos"
logger = logging.getLogger(__name__)


def custom_message_box(parent, title, text, icon, buttons):
    """Helper para mostrar alertas con estilos personalizados."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    
    # Style the message box buttons
    msg.setStyleSheet("""
        QMessageBox QPushButton {
            background-color: #18181B;
            color: #FAFAFA;
            border: 1px solid #18181B;
            border-radius: 6px;
            padding: 4px 8px;
            font-weight: 500;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #27272A;
        }
        QMessageBox QPushButton:pressed {
            background-color: #09090B;
        }
    """)
    return msg.exec()


class AutoAssignDialog(QDialog):
    """Diálogo para configurar la asignación automática de reuniones."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.setModal(True)
        self.setFixedSize(1200, 600)
        
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
            "DESTRUCTIVE": "#EF4444",
            "ACCENT": theme.colors.surface_secondary,
        }

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.COLORS['BACKGROUND']};
            }}
            QLabel {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 14px;
            }}
            QMessageBox QPushButton {{
                background-color: #18181B;
                color: #FAFAFA;
                border: 1px solid #18181B;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 500;
                min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #27272A;
            }}
            QMessageBox QPushButton:pressed {{
                background-color: #09090B;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("Automatic Assignment")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Review and assign meetings automatically.")
        desc.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']};")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addLayout(header_layout)
        
        # Filter Layout
        filter_layout = QHBoxLayout()
        
        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by Instructor...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 8px 12px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid #18181B;
            }}
        """)
        self.search_input.textChanged.connect(self.filter_table)

        # Status Filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Assigned", "To Update", "Not Found"])
        self.filter_combo.setFixedHeight(36)
        self.filter_combo.setFixedWidth(150)
        self.filter_combo.setStyleSheet(f"""
            QComboBox {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px 8px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QComboBox:hover, QComboBox:focus {{
                border: 1px solid #18181B;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                font-family: 'IBM Plex Sans', sans-serif;
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                selection-background-color: {self.COLORS['ACCENT']};
                selection-color: {self.COLORS['TEXT_PRIMARY']};
                padding: 4px;
            }}
        """)
        self.filter_combo.currentTextChanged.connect(self.filter_table)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Progress bar
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

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "", "Status", "Meeting ID", "Time", "Instructor", "Program/Group", "Reason"
        ])
        
        # Custom Header with Checkbox
        self.header = CheckBoxHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(self.header)
        self.header.setSectionsClickable(True)
        self.header.checkBoxClicked.connect(self.toggle_all_rows)
        
        # Table configuration
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)
        
        # Table Styles
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            QTableWidget::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            QHeaderView::section {{
                background-color: #F4F4F5;
                color: {self.COLORS['TEXT_SECONDARY']};
                padding: 12px;
                border: none;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                font-weight: 600;
                font-family: 'IBM Plex Sans', sans-serif;
            }}
            QScrollBar:vertical {{
                border: none; background: {self.COLORS['SURFACE']};
                width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLORS['BORDER']};
                min-height: 40px; border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # Column widths
        self.table.setColumnWidth(0, 40)   # Checkbox
        self.table.setColumnWidth(1, 100)  # Status
        self.table.setColumnWidth(2, 120)  # Meeting ID
        self.table.setColumnWidth(3, 120)  # Time
        self.table.setColumnWidth(4, 180)  # Instructor
        self.table.setColumnWidth(5, 400)  # Program
        
        layout.addWidget(self.table)
        
        # Connect selection signals
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # Status Summary (Left side)
        self.lbl_to_update = QLabel("To Update: 0")
        self.lbl_to_update.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_to_update)

        self.lbl_assigned = QLabel("Assigned: 0")
        self.lbl_assigned.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_assigned)
        
        self.lbl_not_found = QLabel("Not Found: 0")
        self.lbl_not_found.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_not_found)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['BACKGROUND']};
                color: {self.COLORS['TEXT_PRIMARY']};
                border: 1px solid {self.COLORS['BORDER']};
            }}
            QPushButton:hover {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.start_btn = QPushButton("Execute")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['PRIMARY']};
                color: {self.COLORS['PRIMARY_FOREGROUND']};
                border: 1px solid {self.COLORS['PRIMARY']};
            }}
            QPushButton:hover {{
                background-color: #27272A;
            }}
            QPushButton:disabled {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_SECONDARY']};
                border: 1px solid {self.COLORS['BORDER']};
            }}
        """)
        self.start_btn.clicked.connect(self.execute_assignment)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)
        
        # Reference to schedules (passed from parent)
        self.schedules = []

        # Hover Delegate
        self.table.setMouseTracking(True)
        self.hover_delegate = RowHoverDelegate(self.table)
        self.table.setItemDelegate(self.hover_delegate)
        self.table.cellEntered.connect(self.on_cell_entered)
        self.table.cellClicked.connect(self.on_cell_clicked)

        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)

    def on_cell_entered(self, row, column):
        """Maneja el evento de hover en las celdas."""
        self.hover_delegate.hover_row = row
        
        item = self.table.item(row, column)
        if column == 2 and item and item.data(Qt.ItemDataRole.UserRole):
            self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.table.setCursor(Qt.CursorShape.ArrowCursor)
             
        self.table.viewport().update()

    def on_cell_clicked(self, row, column):
        """Maneja el clic en las celdas (para abrir links)."""
        if column == 2:  # Meeting ID
            item = self.table.item(row, column)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    QDesktopServices.openUrl(QUrl(url))

    def open_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {self.COLORS['BACKGROUND']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {self.COLORS['TEXT_PRIMARY']};
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
            }}
        """)
        deselect_action = menu.addAction("Deselect All")
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == deselect_action:
            self.deselect_all_rows()

    def deselect_all_rows(self):
        self.table.clearSelection()

    def toggle_all_rows(self, state: bool):
        """Marca o desmarca todas las filas."""
        self.table.blockSignals(True)
        try:
            check_state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
            
            if state:
                self.table.selectAll()
            else:
                self.table.clearSelection()
                
            for i in range(self.table.rowCount()):
                if self.table.isRowHidden(i):
                    continue
                    
                item = self.table.item(i, 0)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                    item.setCheckState(check_state)
        finally:
            self.table.blockSignals(False)
            self.update_execute_button_text()

    def on_selection_changed(self):
        """Sincroniza la selección de filas con los checkboxes."""
        if self.table.signalsBlocked():
            return

        self.table.blockSignals(True)
        try:
            selected_rows = {index.row() for index in self.table.selectedIndexes()}
            
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if not item or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                    continue
                
                should_be_checked = i in selected_rows
                current_state = item.checkState() == Qt.CheckState.Checked
                
                if should_be_checked != current_state:
                    item.setCheckState(Qt.CheckState.Checked if should_be_checked else Qt.CheckState.Unchecked)
        finally:
            self.table.blockSignals(False)
            self.update_execute_button_text()

    def on_item_changed(self, item):
        """Sincroniza los checkboxes con la selección de filas."""
        if item.column() == 0:
            if self.table.signalsBlocked():
                return

            self.table.blockSignals(True)
            try:
                row = item.row()
                selection_model = self.table.selectionModel()
                if item.checkState() == Qt.CheckState.Checked:
                    selection_model.select(
                        self.table.model().index(row, 0),
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                    )
                else:
                    selection_model.select(
                        self.table.model().index(row, 0),
                        QItemSelectionModel.SelectionFlag.Deselect | QItemSelectionModel.SelectionFlag.Rows
                    )
                
                if item.checkState() == Qt.CheckState.Unchecked and self.header.isOn:
                    self.header.isOn = False
                    self.header.viewport().update()
            finally:
                self.table.blockSignals(False)
                self.update_execute_button_text()

    def process_data(self):
        """Inicia el procesamiento de datos (búsqueda de coincidencias)."""
        logger.debug(f"process_data called. Schedules count: {len(self.schedules)}")
        if not self.schedules:
            return
            
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.table.setRowCount(0)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = AssignmentWorker(self.schedules)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()
        
    def update_progress(self, msg):
        self.setWindowTitle(f"{APP_NAME} | Auto Assign - {msg}")

    def on_processing_finished(self, results, errors):
        """Maneja los resultados del procesamiento."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Execute")
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.progress_bar.setVisible(False)
        
        if errors:
            custom_message_box(
                self, "Error", f"Errors occurred: {'; '.join(errors[:3])}",
                QMessageBox.Icon.Critical, QMessageBox.StandardButton.Ok
            )
            return
            
        self.table.setRowCount(len(results))
        self.table.setSortingEnabled(False)
        
        to_update_count = 0
        assigned_count = 0
        not_found_count = 0
        
        for i, res in enumerate(results):
            schedule = res["schedule"]
            status = res["status"]
            meeting_id = res["meeting_id"]
            reason = res["reason"]
            
            if status == "assigned":
                assigned_count += 1
            elif status == "to_update":
                to_update_count += 1
            else:
                not_found_count += 1
            
            found_instructor = res.get("found_instructor")
            
            # Checkbox
            chk_item = QTableWidgetItem()
            
            if status == "to_update":
                chk_item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                if found_instructor:
                    chk_item.setData(Qt.ItemDataRole.UserRole, found_instructor)
            else:
                chk_item.setFlags(Qt.ItemFlag.NoItemFlags)

            self.table.setItem(i, 0, chk_item)
            
            # Status
            display_status = "Not Found"
            color = QColor("#EF4444")  # Red
            
            if status == "assigned":
                display_status = "Assigned"
                color = QColor("#10B981")  # Green
            elif status == "to_update":
                display_status = "To Update"
                color = QColor("#F59E0B")  # Amber
            
            status_item = QTableWidgetItem(display_status)
            status_item.setForeground(color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status != "to_update":
                status_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(i, 1, status_item)
            
            # Helper para crear items
            def create_item(text, align_center=False):
                it = QTableWidgetItem(str(text))
                if align_center:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if status != "to_update":
                    it.setFlags(Qt.ItemFlag.NoItemFlags)
                else:
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                return it

            # Meeting ID
            meeting_id_item = create_item(str(meeting_id), align_center=True)
            if meeting_id and str(meeting_id) != "-" and str(meeting_id) != "":
                meeting_id_item.setForeground(QColor("#2563EB"))
                font = meeting_id_item.font()
                font.setUnderline(True)
                meeting_id_item.setFont(font)
                meeting_id_item.setData(Qt.ItemDataRole.UserRole, f"https://zoom.us/meeting/{meeting_id}")
                if status == "to_update":
                    meeting_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                else:
                    meeting_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                 
            self.table.setItem(i, 2, meeting_id_item)
            
            # Time
            start_24h = schedule._convert_to_24h(schedule.start_time)
            end_24h = schedule._convert_to_24h(schedule.end_time)
            self.table.setItem(i, 3, create_item(f"{start_24h} - {end_24h}", align_center=True))
            
            # Instructor
            self.table.setItem(i, 4, create_item(schedule.instructor))
            
            # Program
            self.table.setItem(i, 5, create_item(schedule.program))
            
            # Reason
            self.table.setItem(i, 6, create_item(reason, align_center=True))
            
        self.lbl_to_update.setText(f"To Update: {to_update_count}")
        self.lbl_assigned.setText(f"Assigned: {assigned_count}")
        self.lbl_not_found.setText(f"Not Found: {not_found_count}")
            
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.AscendingOrder)
        self.filter_table()
        self.update_execute_button_text()
        
    def filter_table(self, text=None):
        """Filtra la tabla según el estado seleccionado y el texto de búsqueda."""
        status_filter = self.filter_combo.currentText()
        search_text = self.search_input.text().lower().strip()
        
        search_terms = [term.strip() for term in search_text.split(',') if term.strip()]
        
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 1)
            if not status_item:
                continue
            
            status = status_item.text()
            status_match = (status_filter == "All") or (status_filter == status)
            
            instructor_item = self.table.item(row, 4)
            instructor_name = instructor_item.text().lower() if instructor_item else ""
            
            if not search_terms:
                search_match = True
            else:
                search_match = any(term in instructor_name for term in search_terms)
            
            self.table.setRowHidden(row, not (status_match and search_match))

    def update_execute_button_text(self):
        """Actualiza el texto del botón Execute con la cantidad de filas seleccionadas."""
        count = sum(
            1 for i in range(self.table.rowCount())
            if (item := self.table.item(i, 0)) and item.checkState() == Qt.CheckState.Checked
        )
        
        self.start_btn.setText(f"Execute ({count})" if count > 0 else "Execute")

    def execute_assignment(self):
        """Ejecuta la asignación para las filas seleccionadas."""
        assignments = []
        
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                found_instructor = item.data(Qt.ItemDataRole.UserRole)
                meeting_id_item = self.table.item(i, 2)
                program_item = self.table.item(i, 5)
                
                if found_instructor and meeting_id_item:
                    assignments.append({
                        "meeting_id": meeting_id_item.text(),
                        "new_host_email": found_instructor.get("email"),
                        "new_host_id": found_instructor.get("id"),
                        "topic": program_item.text() if program_item else "Unknown Meeting"
                    })
        
        if not assignments:
            custom_message_box(
                self, "Warning", "No meetings selected for assignment.",
                QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok
            )
            return
            
        confirm = custom_message_box(
            self, 
            "Confirm Assignment", 
            f"Are you sure you want to assign {len(assignments)} meetings?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Updating...")
        self.cancel_btn.setEnabled(False)
        self.table.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.update_worker = UpdateWorker(assignments)
        self.update_worker.progress.connect(self.update_progress)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.start()

    def on_update_finished(self, successes, errors):
        """Maneja el fin de la actualización."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Execute")
        self.cancel_btn.setEnabled(True)
        self.table.setEnabled(True)
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.progress_bar.setVisible(False)
        
        msg = f"Process completed.\n\nSuccess: {len(successes)}\nErrors: {len(errors)}"
        
        if errors:
            msg += "\n\nFirst few errors:\n" + "\n".join(errors[:3])
            custom_message_box(
                self, "Completed with Errors", msg,
                QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok
            )
        else:
            custom_message_box(
                self, "Success", msg,
                QMessageBox.Icon.Information, QMessageBox.StandardButton.Ok
            )
            
        # Recargar datos para reflejar cambios
        self.process_data()


__all__ = ["AutoAssignDialog"]
