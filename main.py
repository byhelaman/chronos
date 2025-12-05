"""
Chronos v2 - Main Entry Point
New init flow: Setup Wizard → Login → Main App
No hardcoded secrets, no .env required
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtCore import Qt

# Import new v2 modules
from app.config import config
from app.services.auth_service import auth_service
from app.services.session_service import session_service
from app.ui.dialogs.setup_wizard import SetupWizard
from app.ui.dialogs.login_dialog import LoginDialog

# Import existing modules that still work
from version_manager import version_manager, CURRENT_VERSION as APP_VERSION


def show_setup_wizard() -> bool:
    """
    Show setup wizard for first-time configuration.
    Returns True if setup completed, False if cancelled.
    """
    wizard = SetupWizard()
    result = wizard.exec()
    return result == QDialog.DialogCode.Accepted


def show_login_dialog() -> bool:
    """
    Show login dialog.
    Returns True if login successful, False if cancelled.
    """
    dialog = LoginDialog()
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted:
        # Set authenticated client in auth_service
        auth_service.set_client(dialog.supabase_client)
        auth_service.set_user_info(dialog.user_info)
        return True
    
    return False


def try_restore_session() -> bool:
    """
    Try to restore saved session.
    Returns True if session restored, False otherwise.
    """
    print("Checking for saved session...")
    session_data = session_service.load_session()
    
    if session_data:
        supabase_client, user_info = session_data
        auth_service.set_client(supabase_client)
        auth_service.set_user_info(user_info)
        print(f"✓ Session restored for {user_info.get('email', 'user')}")
        return True
    
    return False


def main():
    """Main entry point for Chronos v2"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Chronos")
    app.setApplicationVersion(APP_VERSION)
    
    # Show splash screen immediately
    from app.ui.splash_screen import SplashScreen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    
    # =====================================================
    # STEP 1: Check if app is configured
    # =====================================================
    if not config.is_configured():
        print("First run detected. Starting Setup Wizard...")
        splash.close()  # Hide splash for wizard
        
        if not show_setup_wizard():
            print("Setup cancelled by user")
            sys.exit(0)
        
        # Reload config after wizard
        if not config.is_configured():
            QMessageBox.critical(
                None, 
                "Configuration Error",
                "Setup was not completed. Please restart the application."
            )
            sys.exit(1)
    
    # =====================================================
    # STEP 2: Try to restore session or show login
    # =====================================================
    if not try_restore_session():
        print("No valid session found. Showing login...")
        splash.close()  # Hide splash for login dialog
        
        if not show_login_dialog():
            print("Login cancelled by user")
            sys.exit(0)
    
    # =====================================================
    # STEP 3: Launch main application
    # =====================================================
    print("Starting main application...")
    
    # Import main window here to avoid circular imports
    # and ensure auth is set up first
    try:
        # Import from legacy (will be migrated to app/ui/main_window.py later)
        from app_legacy import SchedulePlanner
        
        window = SchedulePlanner()
        
        # Close splash and show main window
        splash.finish(window)
        
        # =====================================================
        # STEP 4: Check for updates in background (non-blocking)
        # =====================================================
        def on_update_available(version, url, notes):
            from app.ui.dialogs.update_dialog import UpdateDialog
            update_info = {"version": version, "url": url, "notes": notes}
            dialog = UpdateDialog(update_info, parent=window)
            result = dialog.exec()
            if result == QDialog.DialogCode.Rejected:
                window.close()
        
        version_manager.update_available.connect(on_update_available)
        version_manager.check_for_updates()
        
        # Cleanup on exit
        def cleanup():
            print("Application closing...")
        
        app.aboutToQuit.connect(cleanup)
        
        sys.exit(app.exec())
        
    except ImportError as e:
        # If main.py can't be imported, show error
        QMessageBox.critical(
            None,
            "Import Error",
            f"Could not import main application:\n{str(e)}\n\n"
            "Make sure all dependencies are installed."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
