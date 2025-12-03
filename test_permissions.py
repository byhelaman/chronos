"""
Chronos - Test Permissions
Script para verificar la lógica de permisos.
"""

import unittest
from unittest.mock import MagicMock, patch
from auth_manager import AuthManager
from permissions import ASSIGNMENT_AUTO, MEETING_SEARCH

class TestPermissions(unittest.TestCase):
    
    def setUp(self):
        self.auth_manager = AuthManager()
        self.mock_supabase = MagicMock()
        self.auth_manager._supabase = self.mock_supabase
        
        # Mock current user
        self.mock_user = MagicMock()
        self.mock_user.id = "test-user-id"
        self.mock_user.email = "test@example.com"
        self.auth_manager._current_user = self.mock_user

    def test_has_permission_admin(self):
        """Test que un admin tiene permisos"""
        # Mock get_user_info response
        with patch.object(self.auth_manager, 'get_user_info') as mock_get_info:
            mock_get_info.return_value = {
                "role": "admin",
                "permissions": [ASSIGNMENT_AUTO, MEETING_SEARCH]
            }
            
            self.assertTrue(self.auth_manager.has_permission(ASSIGNMENT_AUTO))
            self.assertTrue(self.auth_manager.has_permission(MEETING_SEARCH))
            self.assertFalse(self.auth_manager.has_permission("non_existent_permission"))

    def test_has_permission_user(self):
        """Test que un usuario normal tiene permisos limitados"""
        with patch.object(self.auth_manager, 'get_user_info') as mock_get_info:
            mock_get_info.return_value = {
                "role": "user",
                "permissions": [MEETING_SEARCH]
            }
            
            self.assertFalse(self.auth_manager.has_permission(ASSIGNMENT_AUTO))
            self.assertTrue(self.auth_manager.has_permission(MEETING_SEARCH))

    def test_custom_permissions(self):
        """Test que los permisos personalizados funcionan"""
        with patch.object(self.auth_manager, 'get_user_info') as mock_get_info:
            mock_get_info.return_value = {
                "role": "user",
                "permissions": [MEETING_SEARCH, "custom:perm"]
            }
            
            self.assertTrue(self.auth_manager.has_permission("custom:perm"))

    def test_user_management(self):
        """Test user management methods (mocked)"""
        # Mock supabase client
        mock_client = MagicMock()
        self.auth_manager._supabase = mock_client
        
        # Test get_all_users
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "u1", "role": "admin"}, {"user_id": "u2", "role": "user"}]
        mock_client.table.return_value.select.return_value.execute.return_value = mock_response
        
        users = self.auth_manager.get_all_users()
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]["role"], "admin")
        
        # Test update_user_role
        self.auth_manager.update_user_role("u2", "admin")
        mock_client.table.return_value.update.assert_called_with({"role": "admin"})
        mock_client.table.return_value.update.return_value.eq.assert_called_with("user_id", "u2")

if __name__ == '__main__':
    unittest.main()
