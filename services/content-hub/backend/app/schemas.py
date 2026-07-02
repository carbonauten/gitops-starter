from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ArticleCreate(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = ""
    status: Literal["draft", "published"] = "draft"
    template: Optional[str] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = None
    status: Optional[Literal["draft", "published"]] = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    content: str
    status: str
    template: Optional[str]
    author_id: str
    author_name: str
    author_email: str
    created_at: datetime
    updated_at: datetime


class FileResponse(BaseModel):
    id: str
    original_name: str
    content_type: str
    size_bytes: int
    folder: str
    uploaded_by_id: str
    uploaded_by_name: str
    created_at: datetime


class SearchResult(BaseModel):
    type: Literal["article", "file"]
    id: str
    title: str
    snippet: str
    status: Optional[str] = None
    folder: Optional[str] = None
    updated_at: datetime


class DashboardStats(BaseModel):
    drafts: int
    published: int
    files: int
    certificates: int
