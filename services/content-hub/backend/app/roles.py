from __future__ import annotations

ROLE_IT_MASTER = "it_master"
ROLE_EDITOR = "editor"
ROLE_CERT_MANAGER = "certificate_manager"
ROLE_VIEWER = "viewer"

ALL_ROLES = (ROLE_IT_MASTER, ROLE_EDITOR, ROLE_CERT_MANAGER, ROLE_VIEWER)
EDIT_ROLES = (ROLE_IT_MASTER, ROLE_EDITOR, ROLE_CERT_MANAGER)
ADMIN_ROLES = (ROLE_IT_MASTER,)
APPROVAL_ROLES = (ROLE_IT_MASTER,)
CERT_APPROVAL_ROLES = (ROLE_IT_MASTER, ROLE_CERT_MANAGER)

ARTICLE_STATUSES = ("draft", "review", "rejected", "scheduled", "published")
EDITABLE_ARTICLE_STATUSES = ("draft", "rejected")


def can_edit(role: str) -> bool:
    return role in EDIT_ROLES


def can_administer_users(role: str) -> bool:
    return role in ADMIN_ROLES


def can_approve_content(role: str) -> bool:
    return role in APPROVAL_ROLES


def can_approve_certificate_renewal(role: str) -> bool:
    return role in CERT_APPROVAL_ROLES
