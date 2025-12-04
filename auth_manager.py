"""
Compatibility shim: auth_manager
Redirects to new app.services.auth_service
"""
from app.services.auth_service import auth_service as _auth
from app.config import config as _config


class _AuthManagerCompat:
    """Compatibility wrapper for old auth_manager interface"""
    
    # Class attributes that main.py expects
    SUPABASE_URL = ""
    SUPABASE_ANON_KEY = ""
    
    def __init__(self):
        self._update_urls()
    
    def _update_urls(self):
        # Update from config if available
        if _config.is_configured():
            _AuthManagerCompat.SUPABASE_URL = _config.supabase_url
            _AuthManagerCompat.SUPABASE_ANON_KEY = _config.supabase_anon_key
    
    def login(self, email: str, password: str):
        return _auth.login(email, password)
    
    def set_client(self, client):
        _auth.set_client(client)
    
    def get_client(self):
        return _auth.get_client()
    
    def has_permission(self, permission: str):
        return _auth.has_permission(permission)
    
    def get_permissions(self):
        return _auth.get_permissions()


# Create singleton instance
auth_manager = _AuthManagerCompat()
