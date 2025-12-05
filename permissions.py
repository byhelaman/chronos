"""
Chronos - Permissions Definitions
Must match the permissions in schema.sql roles table.
"""

# --- Permission Constants ---
# These must match exactly what's in the database

# Schedule Permissions
VIEW_SCHEDULES = "view_schedules"
EDIT_SCHEDULES = "edit_schedules"

# Meeting Permissions
VIEW_MEETINGS = "view_meetings"

# Assignment Permissions
AUTO_ASSIGN = "auto_assign"
MEETING_SEARCH = "meeting_search"
CREATE_LINKS = "create_links"

# Admin wildcard
ALL = "*"

# --- Default Roles Configuration ---
# Mirror of what's in schema.sql

DEFAULT_ROLES = {
    "admin": [ALL],  # Full access
    "manager": [
        VIEW_SCHEDULES,
        EDIT_SCHEDULES,
        VIEW_MEETINGS,
        AUTO_ASSIGN,
        MEETING_SEARCH,
        CREATE_LINKS
    ],
    "user": [
        VIEW_SCHEDULES,
    ]
}


def has_permission(user_permissions: list, required: str) -> bool:
    """Check if user has the required permission."""
    if ALL in user_permissions:
        return True
    return required in user_permissions
