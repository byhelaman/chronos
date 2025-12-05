"""
Chronos - Update Dialog
Mandatory update dialog that blocks app usage until user updates.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from version_manager import version_manager, CURRENT_VERSION


class UpdateDialog(QDialog):
    """Mandatory update dialog - blocks app until updated or closed."""
    
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.version = update_info.get("version", "")
        self.url = update_info.get("url", "")
        self.notes = update_info.get("notes", "")
        
        self.setWindowTitle("Update Required")
        self.setFixedSize(450, 350)
        self.setModal(True)
        # Disable close button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "favicon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Update Required")
        title.setFont(QFont("IBM Plex Sans", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Version info
        version_text = QLabel(f"Current: v{CURRENT_VERSION}  →  New: v{self.version}")
        version_text.setFont(QFont("IBM Plex Sans", 11))
        version_text.setStyleSheet("color: #71717A;")
        layout.addWidget(version_text)
        
        # Message
        message = QLabel("A new version is available. You must update to continue using Chronos.")
        message.setFont(QFont("IBM Plex Sans", 10))
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Release notes
        if self.notes:
            notes_label = QLabel("Release Notes:")
            notes_label.setFont(QFont("IBM Plex Sans", 10, QFont.Weight.Medium))
            layout.addWidget(notes_label)
            
            notes_text = QTextEdit()
            notes_text.setPlainText(self.notes)
            notes_text.setReadOnly(True)
            notes_text.setMaximumHeight(100)
            notes_text.setFont(QFont("IBM Plex Sans", 9))
            layout.addWidget(notes_text)
        
        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("IBM Plex Sans", 10))
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.exit_btn = QPushButton("Exit")
        self.exit_btn.setFixedSize(100, 36)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.exit_btn)
        
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setFixedSize(120, 36)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setDefault(True)
        btn_layout.addWidget(self.update_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            }
            QLabel { color: #09090B; }
            QTextEdit {
                background-color: #F4F4F5;
                border: 1px solid #E4E4E7;
                border-radius: 6px;
                padding: 8px;
            }
            QProgressBar {
                border: 1px solid #E4E4E7;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #18181B;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #18181B;
                color: #FAFAFA;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #27272A; }
            QPushButton:disabled { background-color: #A1A1AA; }
            QPushButton#exitBtn {
                background-color: #FFFFFF;
                color: #09090B;
                border: 1px solid #E4E4E7;
            }
            QPushButton#exitBtn:hover { background-color: #F4F4F5; }
        """)
        self.exit_btn.setObjectName("exitBtn")
    
    def _connect_signals(self):
        self.exit_btn.clicked.connect(self.reject)
        self.update_btn.clicked.connect(self._start_update)
        
        # Connect to version_manager signals
        version_manager.download_progress.connect(self._on_progress)
        version_manager.download_complete.connect(self._on_complete)
        version_manager.error.connect(self._on_error)
    
    def _start_update(self):
        """Start downloading the update."""
        self.update_btn.setEnabled(False)
        self.exit_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Downloading update...")
        
        version_manager.download_update(self.url)
    
    def _on_progress(self, percent: int):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"Downloading update... {percent}%")
    
    def _on_complete(self, file_path: str):
        self.status_label.setText("Installing update...")
        self.progress_bar.setValue(100)
        # Apply update (this will close the app and restart)
        version_manager.apply_update(file_path)
    
    def _on_error(self, error_msg: str):
        self.status_label.setText(f"Error: {error_msg}")
        self.status_label.setStyleSheet("color: #dc2626;")
        self.exit_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Retry")
