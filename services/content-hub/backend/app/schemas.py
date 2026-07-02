from __future__ import annotations

from datetime import date, datetime
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
    type: Literal["article", "file", "certificate"]
    id: str
    title: str
    snippet: str
    status: Optional[str] = None
    folder: Optional[str] = None
    updated_at: datetime


class CertificateCreate(BaseModel):
    name: str = Field(max_length=500)
    category: Literal["compliance", "product", "training", "ssl"] = "compliance"
    issuer: str = Field(default="", max_length=500)
    valid_from: date
    valid_to: date
    renewal_in_progress: bool = False
    responsible_name: str = Field(default="", max_length=200)
    responsible_email: str = Field(default="", max_length=200)
    file_asset_id: Optional[str] = None
    notes: str = ""


class CertificateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=500)
    category: Optional[Literal["compliance", "product", "training", "ssl"]] = None
    issuer: Optional[str] = Field(default=None, max_length=500)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    renewal_in_progress: Optional[bool] = None
    responsible_name: Optional[str] = Field(default=None, max_length=200)
    responsible_email: Optional[str] = Field(default=None, max_length=200)
    file_asset_id: Optional[str] = None
    notes: Optional[str] = None


class CertificateResponse(BaseModel):
    id: str
    name: str
    category: str
    issuer: str
    valid_from: date
    valid_to: date
    renewal_in_progress: bool
    status: str
    days_until_expiry: int
    responsible_name: str
    responsible_email: str
    file_asset_id: Optional[str]
    file_name: Optional[str] = None
    notes: str
    created_by_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class DashboardStats(BaseModel):
    drafts: int
    published: int
    files: int
    certificates: int
    expiring_30: int = 0
    expiring_60: int = 0
    expiring_90: int = 0
