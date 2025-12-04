"""
Compatibility shim: session_manager
Redirects to new app.services.session_service
"""
from app.services.session_service import session_service as _session
from app.services.auth_service import auth_service as _auth


class _SessionManagerCompat:
    """Compatibility wrapper for old session_manager interface"""
    
    def save_session(self, supabase, user_info, config=None):
        """Save session - config parameter ignored (no longer encrypted)"""
        _session.save_session(supabase, user_info)
    
    def load_session(self):
        """Load session - returns tuple for compatibility"""
        result = _session.load_session()
        if result:
            supabase, user_info = result
            # Old code expects (supabase, user_info, config)
            # We return empty dict for config
            return (supabase, user_info, {})
        return None
    
    def clear_session(self):
        """Clear saved session"""
        _session.clear_session()


session_manager = _SessionManagerCompat()
