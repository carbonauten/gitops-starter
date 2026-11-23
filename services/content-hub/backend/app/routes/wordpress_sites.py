from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_wordpress_manager
from ..wordpress_rest_service import (
    check_site_status,
    create_post,
    list_plugins,
    list_posts,
    set_plugin_status,
    update_post,
)
from ..wordpress_site_config_service import (
    create_wordpress_site,
    delete_wordpress_site,
    get_wordpress_site_credentials,
    list_wordpress_sites,
)

router = APIRouter(prefix="/api/wordpress/sites", tags=["wordpress-sites"])


class WordPressSiteCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., min_length=1, max_length=500)
    username: str = Field(..., min_length=1, max_length=200)
    app_password: str = Field(..., min_length=1, max_length=300)


class WordPressPostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=50000)
    status: str = Field(default="draft", description="draft, publish, pending, or private")


class WordPressPostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None, max_length=50000)
    status: Optional[str] = Field(default=None, description="draft, publish, pending, or private")


class WordPressPluginStatusUpdate(BaseModel):
    status: str = Field(..., description="active or inactive")


@router.get("")
def get_sites(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
) -> dict:
    return {"sites": list_wordpress_sites(db)}


@router.post("", status_code=201)
def post_site(
    payload: WordPressSiteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
) -> dict:
    site = create_wordpress_site(
        db,
        label=payload.label,
        base_url=payload.base_url,
        username=payload.username,
        app_password=payload.app_password,
        actor=user,
    )
    log_audit(db, entity_type="wordpress_site", entity_id=site["id"], action="created", actor=user)
    return {"site": site}


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
):
    delete_wordpress_site(db, site_id)
    log_audit(db, entity_type="wordpress_site", entity_id=site_id, action="deleted", actor=user)


@router.get("/{site_id}/status")
async def get_site_status(
    site_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    return await check_site_status(creds)


@router.get("/{site_id}/posts")
async def get_site_posts(
    site_id: str,
    status: str = "any",
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    return {"posts": await list_posts(creds, status=status)}


@router.post("/{site_id}/posts", status_code=201)
async def post_site_post(
    site_id: str,
    payload: WordPressPostCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    post = await create_post(creds, title=payload.title, content=payload.content, status=payload.status)
    log_audit(db, entity_type="wordpress_site_post", entity_id=f"{site_id}:{post['id']}", action="created", actor=user)
    return {"post": post}


@router.patch("/{site_id}/posts/{post_id}")
async def patch_site_post(
    site_id: str,
    post_id: int,
    payload: WordPressPostUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    fields = {key: value for key, value in payload.model_dump().items() if value is not None}
    post = await update_post(creds, post_id, **fields)
    log_audit(db, entity_type="wordpress_site_post", entity_id=f"{site_id}:{post_id}", action="updated", actor=user)
    return {"post": post}


@router.get("/{site_id}/plugins")
async def get_site_plugins(
    site_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    return {"plugins": await list_plugins(creds)}


@router.patch("/{site_id}/plugins/{plugin:path}")
async def patch_site_plugin(
    site_id: str,
    plugin: str,
    payload: WordPressPluginStatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
) -> dict:
    creds = get_wordpress_site_credentials(db, site_id)
    result = await set_plugin_status(creds, plugin, payload.status)
    log_audit(
        db,
        entity_type="wordpress_site_plugin",
        entity_id=f"{site_id}:{plugin}",
        action="status_updated",
        actor=user,
        details={"status": payload.status},
    )
    return {"plugin": result}
