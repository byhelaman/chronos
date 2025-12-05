"""
Chronos v2 - Session Service
Manages session persistence for auto-login.
SECURE STORAGE - Uses system keyring for token storage.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import keyring

from supabase import create_client, Client

from app.config import config


class SessionService:
    """Session persistence manager using system keyring"""
    
    SESSION_DURATION_DAYS = 7
    SERVICE_NAME = "ChronosApp"
    USERNAME = "session_data"
    
    def __init__(self):
        pass
    
    def save_session(self, supabase: Client, user_info: Dict) -> None:
        """
        Save current session securely.
        
        Args:
            supabase: Authenticated Supabase client
            user_info: User information dict
        """
        try:
            session = supabase.auth.get_session()
            if not session:
                return
            
            # Session data
            session_data = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_at": session.expires_at,
                "user_info": user_info,
                "saved_at": datetime.now().isoformat(),
                "expires_session_at": (datetime.now() + timedelta(days=self.SESSION_DURATION_DAYS)).isoformat()
            }
            
            # Save to keyring
            json_str = json.dumps(session_data)
            keyring.set_password(self.SERVICE_NAME, self.USERNAME, json_str)
            
            print(f"✓ Session saved securely (expires in {self.SESSION_DURATION_DAYS} days)")
        
        except Exception as e:
            print(f"Warning: Could not save session: {e}")
    
    def load_session(self) -> Optional[Tuple[Client, Dict]]:
        """
        Load and validate saved session from keyring.
        
        Returns:
            Tuple (supabase_client, user_info) if session is valid
            None if no session or expired
        """
        try:
            if not config.is_configured():
                return None
            
            # Read session from keyring
            json_str = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
            if not json_str:
                return None
                
            session_data = json.loads(json_str)
            
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
                # First try set_session which should auto-refresh if needed
                supabase.auth.set_session(
                    access_token=session_data["access_token"],
                    refresh_token=session_data["refresh_token"]
                )
                
                # Verify session is still valid
                current_session = supabase.auth.get_session()
                if not current_session:
                    raise Exception("Session not restored")
                
                # Check if tokens rotated and save if needed
                if (current_session.access_token != session_data["access_token"] or 
                    current_session.refresh_token != session_data["refresh_token"]):
                    print("Tokens rotated, updating secure storage...")
                    self.save_session(supabase, session_data["user_info"])
                
            except Exception as e:
                # set_session failed, try explicit refresh
                error_str = str(e).lower()
                if "expired" in error_str or "invalid" in error_str:
                    print(f"JWT expired, attempting refresh...")
                    try:
                        # Try to refresh using the refresh token
                        refresh_response = supabase.auth.refresh_session(session_data["refresh_token"])
                        if refresh_response and refresh_response.session:
                            print("✓ Session refreshed successfully")
                            # Save the new tokens
                            self.save_session(supabase, session_data["user_info"])
                        else:
                            raise Exception("Refresh failed")
                    except Exception as refresh_error:
                        print(f"Could not refresh session: {refresh_error}")
                        self.clear_session()
                        return None
                else:
                    print(f"Could not restore session: {e}")
                    self.clear_session()
                    return None
            
            # ALWAYS refresh user info from database to ensure permissions are up to date
            # This is critical after app updates where session format might have changed
            try:
                from app.services.auth_service import auth_service
                
                # Get fresh user_id - might be stored differently in old sessions
                old_user_info = session_data.get("user_info", {})
                user_id = old_user_info.get("id")
                
                if not user_id:
                    print("Session invalid (no user_id), clearing...")
                    self.clear_session()
                    return None
                
                # Always fetch fresh permissions from database
                user_info = auth_service.get_user_info(supabase, user_id)
                
                # Verify we got valid permissions
                if not user_info.get("permissions"):
                    print("Warning: No permissions found for user")
                
                # Update session data with fresh user info (including fresh permissions)
                self.save_session(supabase, user_info)
                
            except Exception as e:
                print(f"Could not refresh user info: {e}")
                print("Session may be stale, forcing re-login...")
                self.clear_session()
                return None
            
            print(f"✓ Session restored for {user_info.get('email', 'user')}")
            
            return supabase, user_info
        
        except Exception as e:
            print(f"Error loading session: {e}")
            self.clear_session()
            return None
    
    def clear_session(self) -> None:
        """Delete saved session"""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
            print("✓ Session cleared")
        except keyring.errors.PasswordDeleteError:
            pass # Password not found, that's fine
        except Exception as e:
            print(f"Error clearing session: {e}")
    
    def has_saved_session(self) -> bool:
        """Check if a saved session exists"""
        return keyring.get_password(self.SERVICE_NAME, self.USERNAME) is not None


# Global instance
session_service = SessionService()
