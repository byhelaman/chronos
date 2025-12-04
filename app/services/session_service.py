"""
Chronos v2 - Session Service
Manages session persistence for auto-login.
NO ENCRYPTION - Supabase tokens are already signed and secure.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict

from supabase import create_client, Client

from app.config import config, AppConfig


class SessionService:
    """Session persistence manager"""
    
    SESSION_DURATION_DAYS = 7
    
    def __init__(self):
        self.session_path = AppConfig.get_session_path()
    
    def save_session(self, supabase: Client, user_info: Dict) -> None:
        """
        Save current session for future use.
        
        Args:
            supabase: Authenticated Supabase client
            user_info: User information dict
        """
        try:
            session = supabase.auth.get_session()
            if not session:
                return
            
            # Session data - NO encryption needed
            # Supabase tokens are already signed JWTs
            session_data = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_at": session.expires_at,
                "user_info": user_info,
                "saved_at": datetime.now().isoformat(),
                "expires_session_at": (datetime.now() + timedelta(days=self.SESSION_DURATION_DAYS)).isoformat()
            }
            
            # Ensure directory exists
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save as plain JSON
            with open(self.session_path, 'w') as f:
                json.dump(session_data, f)
            
            print(f"✓ Session saved (expires in {self.SESSION_DURATION_DAYS} days)")
        
        except Exception as e:
            print(f"Warning: Could not save session: {e}")
    
    def load_session(self) -> Optional[Tuple[Client, Dict]]:
        """
        Load and validate saved session.
        
        Returns:
            Tuple (supabase_client, user_info) if session is valid
            None if no session or expired
        """
        try:
            if not self.session_path.exists():
                return None
            
            if not config.is_configured():
                return None
            
            # Read session
            with open(self.session_path, 'r') as f:
                session_data = json.load(f)
            
            # Check session expiry
            expires_session_at = datetime.fromisoformat(session_data["expires_session_at"])
            if datetime.now() > expires_session_at:
                print("Session expired, please login again")
                self.clear_session()
                return None
            
            # Create client with saved token
            supabase = create_client(
                config.supabase_url,
                config.supabase_anon_key
            )
            
            # Restore session
            try:
                supabase.auth.set_session(
                    access_token=session_data["access_token"],
                    refresh_token=session_data["refresh_token"]
                )
                
                # Verify session is still valid
                current_session = supabase.auth.get_session()
                if not current_session:
                    print("Session invalid, please login again")
                    self.clear_session()
                    return None
                
            except Exception as e:
                print(f"Could not restore session: {e}")
                self.clear_session()
                return None
            
            user_info = session_data["user_info"]
            print(f"✓ Session restored for {user_info.get('email', 'user')}")
            
            return supabase, user_info
        
        except Exception as e:
            print(f"Error loading session: {e}")
            self.clear_session()
            return None
    
    def clear_session(self) -> None:
        """Delete saved session"""
        try:
            if self.session_path.exists():
                self.session_path.unlink()
                print("✓ Session cleared")
        except Exception as e:
            print(f"Error clearing session: {e}")
    
    def has_saved_session(self) -> bool:
        """Check if a saved session exists"""
        return self.session_path.exists()


# Global instance
session_service = SessionService()
