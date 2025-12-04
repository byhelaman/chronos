"""
Compatibility shim: config_manager
Redirects to new app.config - but most functionality removed since we no longer encrypt config
"""

class _ConfigManagerCompat:
    """Compatibility wrapper - minimal functionality since encryption is removed"""
    
    def fetch_config_from_db(self, supabase):
        """No longer fetches encrypted config from DB - return empty dict"""
        return {}
    
    def validate_config(self, config):
        """Config validation - always returns True since we don't use DB config anymore"""
        return True
    
    def clear_cache(self):
        """No-op - no cache to clear"""
        pass


config_manager = _ConfigManagerCompat()
