from __future__ import annotations

ROLE_IT_MASTER = "it_master"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

ALL_ROLES = (ROLE_IT_MASTER, ROLE_EDITOR, ROLE_VIEWER)
EDIT_ROLES = (ROLE_IT_MASTER, ROLE_EDITOR)
ADMIN_ROLES = (ROLE_IT_MASTER,)


def can_edit(role: str) -> bool:
    return role in EDIT_ROLES


def can_administer_users(role: str) -> bool:
    return role in ADMIN_ROLES
