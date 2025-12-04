"""
Chronos v2 - Setup Wizard
Complete setup wizard: Supabase → Admin → Zoom OAuth
Uses default Qt styling.
"""

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from supabase import create_client
import webbrowser

from app.config import config


class ConnectionTestWorker(QThread):
    """Test Supabase connection in background"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, url: str, key: str):
        super().__init__()
        self.url = url
        self.key = key
    
    def run(self):
        try:
            client = create_client(self.url, self.key)
            client.table("roles").select("name").limit(1).execute()
            self.finished.emit(True, "Connection successful!")
        except Exception as e:
            self.finished.emit(False, str(e))


class ZoomStatusWorker(QThread):
    """Check Zoom OAuth status"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, url: str, key: str):
        super().__init__()
        self.url = url
        self.key = key
    
    def run(self):
        try:
            import httpx
            response = httpx.get(
                f"{self.url}/functions/v1/zoom-oauth?action=status",
                headers={"apikey": self.key},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("configured"):
                    self.finished.emit(True, f"Connected (updated: {data.get('updated_at', 'N/A')})")
                else:
                    self.finished.emit(False, "Not configured")
            else:
                self.finished.emit(False, "Could not check status")
        except Exception as e:
            self.finished.emit(False, str(e))


class WelcomePage(QWizardPage):
    """Welcome page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to Chronos")
        self.setSubTitle("This wizard will configure everything you need.")
        
        layout = QVBoxLayout()
        
        info = QLabel(
            "Setup includes:\n\n"
            "1. Connect to Supabase\n"
            "2. Sign in or create account\n"
            "3. Connect Zoom (optional)\n\n"
            "You'll need:\n"
            "- Supabase Project URL and Anon Key\n"
            "- Zoom OAuth configured in your Supabase Edge Functions"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        self.setLayout(layout)


class SupabasePage(QWizardPage):
    """Configure Supabase connection"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Supabase Configuration")
        self.setSubTitle("Connect to your Supabase project.")
        
        self.connection_tested = False
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Project URL:"))
        self.url_input = QLineEdit()
        self.url_input.textChanged.connect(self._on_change)
        layout.addWidget(self.url_input)
        
        layout.addWidget(QLabel("Anon Key:"))
        self.key_input = QLineEdit()
        self.key_input.textChanged.connect(self._on_change)
        layout.addWidget(self.key_input)
        
        layout.addWidget(QLabel("Find these in Supabase Dashboard > Settings > API"))
        
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test)
        self.status_lbl = QLabel("")
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.status_lbl)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        self.setLayout(layout)
        
        self.registerField("supabase_url*", self.url_input)
        self.registerField("supabase_key*", self.key_input)
    
    def _on_change(self):
        self.connection_tested = False
        self.status_lbl.setText("")
        self.completeChanged.emit()
    
    def _test(self):
        url = self.url_input.text().strip()
        key = self.key_input.text().strip()
        if not url or not key:
            self.status_lbl.setText("Fill both fields")
            return
        
        self.test_btn.setEnabled(False)
        self.status_lbl.setText("Testing...")
        
        self.worker = ConnectionTestWorker(url, key)
        self.worker.finished.connect(self._on_result)
        self.worker.start()
    
    def _on_result(self, success, msg):
        self.test_btn.setEnabled(True)
        if success:
            self.status_lbl.setText("Connected!")
            self.connection_tested = True
        else:
            self.status_lbl.setText(f"Error: {msg[:40]}...")
        self.completeChanged.emit()
    
    def isComplete(self):
        return self.connection_tested


class AdminPage(QWizardPage):
    """Account page - sign in or create account"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Your Account")
        self.setSubTitle("Sign in with your existing account or create a new one.")
        
        self.user_created = False
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Email:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        layout.addWidget(self.email_input)
        
        layout.addWidget(QLabel("Password:"))
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Minimum 6 characters")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pass_input)
        
        layout.addWidget(QLabel("Confirm Password:"))
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.confirm_input)
        
        self.status_lbl = QLabel("")
        layout.addWidget(self.status_lbl)
        
        layout.addStretch()
        self.setLayout(layout)
        
        self.registerField("admin_email*", self.email_input)
        self.registerField("admin_password*", self.pass_input)
    
    def validatePage(self):
        if len(self.pass_input.text()) < 6:
            QMessageBox.warning(self, "Error", "Password must be at least 6 characters.")
            return False
        if self.pass_input.text() != self.confirm_input.text():
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return False
        
        if not self.user_created:
            try:
                url = self.field("supabase_url")
                key = self.field("supabase_key")
                email = self.email_input.text().strip()
                password = self.pass_input.text()
                
                client = create_client(url, key)
                
                # Check if user already exists
                self.status_lbl.setText("Checking if user exists...")
                existing = client.table("user_profiles").select("email").eq("email", email).execute()
                
                if existing.data:
                    # User exists, try to sign in instead
                    self.status_lbl.setText("User exists, signing in...")
                    try:
                        auth_resp = client.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        if auth_resp.user:
                            self.user_created = True
                            self.status_lbl.setText("Signed in!")
                            print(f"Admin user already exists: {email}")
                        else:
                            raise Exception("Sign in failed")
                    except Exception as e:
                        self.status_lbl.setText("Wrong password or account issue")
                        return False
                else:
                    # New user, sign up
                    self.status_lbl.setText("Creating account...")
                    auth_resp = client.auth.sign_up({
                        "email": email,
                        "password": password
                    })
                    
                    if auth_resp.user:
                        self.user_created = True
                        self.status_lbl.setText("Account created!")
                        print(f"Admin user created: {email}")
                    else:
                        raise Exception("Failed to create user")
                    
            except Exception as e:
                error_msg = str(e)
                self.status_lbl.setText(f"Error: {error_msg[:50]}")
                return False
        
        return True


class ZoomPage(QWizardPage):
    """Connect Zoom account"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Connect Zoom")
        self.setSubTitle("Authorize Chronos to access your Zoom account.")
        
        self.zoom_connected = False
        self.supabase_url = ""
        self.supabase_key = ""
        self.access_token = ""
        
        layout = QVBoxLayout()
        
        info = QLabel(
            "Before connecting, make sure you have:\n\n"
            "1. Created a Zoom OAuth App in Zoom Marketplace\n"
            "2. Set the Redirect URI to:\n"
            "   {your-supabase-url}/functions/v1/zoom-oauth\n"
            "3. Added ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET\n"
            "   to your Supabase Edge Function secrets"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect Zoom Account")
        self.connect_btn.clicked.connect(self._connect_zoom)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.status_lbl = QLabel("")
        layout.addWidget(self.status_lbl)
        
        layout.addWidget(QLabel("You can skip this step and configure Zoom later."))
        
        layout.addStretch()
        self.setLayout(layout)
    
    def initializePage(self):
        self.supabase_url = self.field("supabase_url")
        self.supabase_key = self.field("supabase_key")
        # Disable button until status check completes
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Checking...")
        self._check_status()
    
    def _check_status(self):
        self.status_lbl.setText("Checking Zoom status...")
        self.worker = ZoomStatusWorker(self.supabase_url, self.supabase_key)
        self.worker.finished.connect(self._on_status)
        self.worker.start()
    
    def _on_status(self, connected, msg):
        if connected:
            self.status_lbl.setText(f"Zoom is connected! ({msg})")
            self.zoom_connected = True
            self.connect_btn.setText("Connected")
            self.connect_btn.setEnabled(False)
        else:
            self.status_lbl.setText("Zoom not connected yet")
            self.connect_btn.setText("Connect Zoom Account")
            self.connect_btn.setEnabled(True)
        self.completeChanged.emit()
    
    def _connect_zoom(self):
        try:
            import httpx
            
            if not self.access_token:
                email = self.field("admin_email")
                password = self.field("admin_password")
                
                client = create_client(self.supabase_url, self.supabase_key)
                
                self.status_lbl.setText("Authenticating...")
                auth_resp = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if not auth_resp.session:
                    self.status_lbl.setText("Could not authenticate.")
                    return
                
                self.access_token = auth_resp.session.access_token
            
            self.status_lbl.setText("Getting Zoom authorization URL...")
            response = httpx.get(
                f"{self.supabase_url}/functions/v1/zoom-oauth?action=authorize",
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.access_token}"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                auth_url = data.get("authorization_url")
                
                if auth_url:
                    self.status_lbl.setText("Opening browser...")
                    webbrowser.open(auth_url)
                    
                    self.connect_btn.setEnabled(False)
                    self.connect_btn.setText("Waiting...")
                    self._start_polling()
                else:
                    self.status_lbl.setText("No authorization URL received")
            else:
                error = response.json().get("error", "Unknown error")
                self.status_lbl.setText(f"Error: {error}")
                
        except Exception as e:
            self.status_lbl.setText(f"Error: {str(e)[:50]}")
    
    def _start_polling(self):
        self.poll_count = 0
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._poll_status)
        self.poll_timer.start(3000)
    
    def _poll_status(self):
        self.poll_count += 1
        if self.poll_count > 60:
            self.poll_timer.stop()
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Connect Zoom Account")
            self.status_lbl.setText("Timed out. Try again.")
            return
        
        self.worker = ZoomStatusWorker(self.supabase_url, self.supabase_key)
        self.worker.finished.connect(self._on_poll_result)
        self.worker.start()
    
    def _on_poll_result(self, connected, msg):
        if connected:
            self.poll_timer.stop()
            self.status_lbl.setText("Zoom connected successfully!")
            self.zoom_connected = True
            self.connect_btn.setText("Connected")
            self.connect_btn.setEnabled(False)
            self.completeChanged.emit()


class CompletePage(QWizardPage):
    """Setup complete"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Complete!")
        self.setSubTitle("Chronos is ready to use.")
        
        layout = QVBoxLayout()
        
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def initializePage(self):
        email = self.field("admin_email")
        self.summary.setText(
            f"Supabase connected\n"
            f"Admin account created: {email}\n"
            f"Configuration saved\n\n"
            f"Click Finish to start using Chronos!"
        )


class SetupWizard(QWizard):
    """Complete setup wizard"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Chronos Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        self.addPage(WelcomePage())
        self.addPage(SupabasePage())
        self.addPage(AdminPage())
        self.zoom_page = ZoomPage()
        self.addPage(self.zoom_page)
        self.addPage(CompletePage())
        
        self.finished.connect(self._on_finished)
    
    def _on_finished(self, result):
        if result == QWizard.DialogCode.Accepted:
            self._save()
    
    def _save(self):
        url = self.field("supabase_url")
        key = self.field("supabase_key")
        email = self.field("admin_email")
        password = self.field("admin_password")
        
        try:
            config.save(url, key)
            
            client = create_client(url, key)
            
            try:
                auth_resp = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                user_id = auth_resp.user.id
                print(f"Admin user already exists: {email}")
            except:
                auth_resp = client.auth.sign_up({
                    "email": email,
                    "password": password
                })
                if auth_resp.user:
                    user_id = auth_resp.user.id
                    print(f"Admin user created: {email}")
                else:
                    raise Exception("Failed to create user")
            
            # Profile is auto-created by database trigger
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Setup Warning",
                f"Configuration saved but there was an issue:\n{str(e)}"
            )
