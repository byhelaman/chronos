"""
Chronos v2 - Authentication Service
Manages user authentication with Supabase Auth.
"""

from supabase import create_client, Client
from typing import Optional, Tuple, Dict, List

from app.config import config


class AuthService:
    """Authentication service using Supabase Auth"""
    
    def __init__(self):
        self._supabase: Optional[Client] = None
        self._current_user: Optional[Dict] = None
        self._user_info: Optional[Dict] = None
    
    def _get_client(self) -> Client:
        """Get or create Supabase client"""
        if not config.is_configured():
            raise Exception("Application not configured. Please run setup wizard.")
        
        if self._supabase is None:
            self._supabase = create_client(
                config.supabase_url,
                config.supabase_anon_key
            )
        return self._supabase
    
    def login(self, email: str, password: str) -> Tuple[Client, Dict]:
        """
        Authenticate user with email and password.
        
        Returns:
            Tuple (supabase_client, user_info)
        
        Raises:
            Exception: If credentials are invalid or user is not authorized
        """
        try:
            supabase = self._get_client()
            
            # Authenticate
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user:
                raise Exception("Invalid credentials")
            
            user = auth_response.user
            self._current_user = user
            
            # Check if user is authorized
            if not self._is_user_authorized(supabase, user.id):
                raise Exception("User not authorized to access this application")
            
            # Get user info with permissions
            user_info = self._get_user_info(supabase, user.id)
            self._user_info = user_info
            
            return supabase, user_info
        
        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                raise Exception("Incorrect email or password")
            elif "not authorized" in error_msg:
                raise Exception("You are not authorized to access this application")
            else:
                raise Exception(f"Login error: {error_msg}")
    
    def _is_user_authorized(self, supabase: Client, user_id: str) -> bool:
        """Check if user is in user_profiles table"""
        try:
            response = supabase.table("user_profiles")\
                .select("user_id")\
                .eq("user_id", user_id)\
                .execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"Error checking authorization: {e}")
            return False
    
    def _get_user_info(self, supabase: Client, user_id: str) -> Dict:
        """Get user info including role and permissions"""
        try:
            # Get user profile with role
            profile_resp = supabase.table("user_profiles")\
                .select("role")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if not profile_resp.data:
                return {"id": user_id, "role": "user", "permissions": []}
            
            role_name = profile_resp.data.get("role", "user")
            
            # Get role permissions
            role_resp = supabase.table("roles")\
                .select("permissions")\
                .eq("name", role_name)\
                .single()\
                .execute()
            
            role_perms = role_resp.data.get("permissions", []) if role_resp.data else []
            
            return {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": role_name,
                "permissions": role_perms
            }
        
        except Exception as e:
            print(f"Error getting user info: {e}")
            return {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": "user",
                "permissions": []
            }
    
    def has_permission(self, permission: str) -> bool:
        """Check if current user has a specific permission"""
        if not self._user_info:
            return False
        
        permissions = self._user_info.get("permissions", [])
        
        # Admin has all permissions
        if "*" in permissions:
            return True
        
        return permission in permissions
    
    def get_permissions(self) -> List[str]:
        """Get list of current user's permissions"""
        if not self._user_info:
            return []
        return self._user_info.get("permissions", [])
    
    def get_client(self) -> Client:
        """Get authenticated Supabase client"""
        if not self._supabase:
            raise Exception("Not authenticated. Please login first.")
        return self._supabase
    
    def set_client(self, client: Client) -> None:
        """Set Supabase client (for session restore)"""
        self._supabase = client
        if not self._current_user:
            try:
                self._current_user = client.auth.get_user().user
            except:
                pass
    
    def set_user_info(self, user_info: Dict) -> None:
        """Set user info (for session restore)"""
        self._user_info = user_info
    
    def logout(self) -> None:
        """Sign out current user"""
        try:
            if self._supabase:
                self._supabase.auth.sign_out()
        except Exception as e:
            print(f"Error during logout: {e}")
        finally:
            self._supabase = None
            self._current_user = None
            self._user_info = None
    
    def get_current_user(self) -> Optional[Dict]:
        """Get current user info"""
        return self._user_info
    
    @classmethod
    def create_client(cls) -> Client:
        """Create unauthenticated Supabase client"""
        if not config.is_configured():
            raise Exception("Application not configured")
        return create_client(config.supabase_url, config.supabase_anon_key)


# Global instance
auth_service = AuthService()
