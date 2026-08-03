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


class SharePointCertificateImport(BaseModel):
    item_id: str = Field(min_length=1, max_length=200)
    name: Optional[str] = Field(default=None, max_length=500)
    category: Optional[Literal["compliance", "product", "training", "ssl"]] = None
    issuer: str = Field(default="", max_length=500)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    renewal_in_progress: bool = False
    responsible_name: str = Field(default="", max_length=200)
    responsible_email: str = Field(default="", max_length=200)
    escalate_email: str = Field(default="", max_length=200)
    parent_id: Optional[str] = None
    notes: str = ""


class SharePointFileImport(BaseModel):
    item_id: str = Field(min_length=1, max_length=200)
    folder: str = Field(default="certificates", max_length=200)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    slug: Optional[str] = Field(default=None, max_length=200)
    short_description: str = Field(default="", max_length=500)
    description: str = ""
    price_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    sku: str = Field(default="", max_length=100)
    is_published: bool = False
    sort_order: int = 0
    image_file_asset_id: Optional[str] = None
    stock_qty: int = Field(default=0, ge=0)
    track_inventory: bool = False
    vat_rate_bps: int = Field(default=1900, ge=0, le=10000)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    slug: Optional[str] = Field(default=None, max_length=200)
    short_description: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    price_cents: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    sku: Optional[str] = Field(default=None, max_length=100)
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None
    image_file_asset_id: Optional[str] = None
    stock_qty: Optional[int] = Field(default=None, ge=0)
    track_inventory: Optional[bool] = None
    vat_rate_bps: Optional[int] = Field(default=None, ge=0, le=10000)


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    short_description: str
    description: str
    price_cents: int
    currency: str
    sku: str
    is_published: bool
    sort_order: int
    image_file_asset_id: Optional[str] = None
    image_name: Optional[str] = None
    image_url: Optional[str] = None
    stock_qty: int = 0
    track_inventory: bool = False
    vat_rate_bps: int = 1900
    created_by_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime


class ShopProductPublic(BaseModel):
    id: str
    name: str
    slug: str
    short_description: str
    description: str
    price_cents: int
    currency: str
    sku: str
    image_url: Optional[str] = None
    sort_order: int
    vat_rate_bps: int = 1900
    track_inventory: bool = False
    stock_available: Optional[int] = None
    in_stock: bool = True


class ShopCheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=999)


class ShopCheckoutCustomer(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=50)
    company: str = Field(default="", max_length=200)
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: str = Field(default="", max_length=300)
    postal_code: str = Field(min_length=1, max_length=30)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="DE", min_length=2, max_length=2)


class ShopCheckoutRequest(BaseModel):
    items: list[ShopCheckoutItem]
    customer: ShopCheckoutCustomer
    payment_method: Literal["stripe", "invoice"] = "stripe"
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
    products: int = 0
    products_published: int = 0
