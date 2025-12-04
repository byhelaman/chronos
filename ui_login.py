"""
Compatibility shim: ui_login
Redirects to new app.ui.dialogs.login_dialog
"""
from app.ui.dialogs.login_dialog import LoginDialog

# Re-export for compatibility
__all__ = ['LoginDialog']
