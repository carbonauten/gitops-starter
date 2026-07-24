from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ArticleCreate(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = ""
    status: Literal["draft"] = "draft"
    template: Optional[str] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    content: str
    status: str
    template: Optional[str]
    scheduled_publish_at: Optional[datetime] = None
    review_comment: str = ""
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
    folder_id: Optional[str] = None
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
    relevance: Optional[float] = None


class SearchAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: str = "de"
    type: Optional[Literal["article", "file", "certificate"]] = None


class CertificateCreate(BaseModel):
    name: str = Field(max_length=500)
    category: Literal["compliance", "product", "training", "ssl"] = "compliance"
    issuer: str = Field(default="", max_length=500)
    valid_from: date
    valid_to: date
    renewal_in_progress: bool = False
    responsible_name: str = Field(default="", max_length=200)
    responsible_email: str = Field(default="", max_length=200)
    escalate_email: str = Field(default="", max_length=200)
    parent_id: Optional[str] = None
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
    escalate_email: Optional[str] = Field(default=None, max_length=200)
    parent_id: Optional[str] = None
    file_asset_id: Optional[str] = None
    notes: Optional[str] = None


class CertificateChildSummary(BaseModel):
    id: str
    name: str
    status: str
    valid_to: date
    days_until_expiry: int


class CertificateResponse(BaseModel):
    id: str
    name: str
    category: str
    issuer: str
    valid_from: date
    valid_to: date
    renewal_in_progress: bool
    renewal_approval_status: str = "none"
    renewal_review_comment: str = ""
    status: str
    days_until_expiry: int
    responsible_name: str
    responsible_email: str
    escalate_email: str = ""
    parent_id: Optional[str] = None
    parent_name: Optional[str] = None
    children: list[CertificateChildSummary] = []
    file_asset_id: Optional[str]
    file_name: Optional[str] = None
    notes: str
    created_by_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class DashboardStats(BaseModel):
    drafts: int
    in_review: int = 0
    scheduled: int = 0
    published: int
    files: int
    certificates: int
    renewals_pending: int = 0
    expiring_30: int = 0
    expiring_60: int = 0
    expiring_90: int = 0
