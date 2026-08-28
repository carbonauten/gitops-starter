export type User = {
  id: string;
  db_id: string;
  name: string;
  email: string;
  role: "it_master" | "editor" | "certificate_manager" | "viewer";
  role_source?: "manual" | "default" | "entra_group";
  department_id?: string | null;
  department_name?: string | null;
  language: string;
  is_active: boolean;
  can_manage_shop?: boolean;
  last_login_at?: string | null;
};

export type EntraGroupMapping = {
  id: string;
  entra_group_id: string;
  entra_group_name: string;
  role: User["role"];
  created_at?: string | null;
};

export type Department = {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  sort_order: number;
  member_count?: number;
};

export type UserInvite = {
  id: string;
  email: string;
  role: User["role"];
  department_id?: string | null;
  department_name?: string | null;
  invited_by_name: string;
  expires_at: string;
  accepted_at?: string | null;
  created_at: string;
  status: "pending" | "accepted" | "expired";
  invite_url: string;
  email_sent?: boolean;
  email_pending?: boolean;
};

export type PublicInvite = {
  email: string;
  role: User["role"];
  department_name?: string | null;
  invited_by_name: string;
  expires_at: string;
};

export function canEditContent(role: User["role"]): boolean {
  return role === "it_master" || role === "editor" || role === "certificate_manager";
}

export function canApproveContent(role: User["role"]): boolean {
  return role === "it_master";
}

export function canApproveCertificates(role: User["role"]): boolean {
  return role === "it_master" || role === "certificate_manager";
}

export function canManageUsers(role: User["role"]): boolean {
  return role === "it_master";
}

export function canManageShop(user: Pick<User, "role" | "can_manage_shop"> | null | undefined): boolean {
  if (!user) return false;
  if (user.role === "it_master") return true;
  return Boolean(user.can_manage_shop);
}

export type Article = {
  id: string;
  title: string;
  content: string;
  status: "draft" | "review" | "rejected" | "scheduled" | "published";
  template: string | null;
  scheduled_publish_at?: string | null;
  review_comment?: string;
  author_id: string;
  author_name: string;
  author_email: string;
  created_at: string;
  updated_at: string;
};

export type FileAsset = {
  id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  folder: string;
  folder_id?: string | null;
  uploaded_by_id: string;
  uploaded_by_name: string;
  created_at: string;
};

export type FileFolderNode = {
  id: string;
  name: string;
  slug: string;
  parent_id?: string | null;
  path: string;
  children: FileFolderNode[];
};

export type FileBrowseFolder = {
  id: string;
  name: string;
  source: "platform" | "sharepoint" | "onedrive";
  path?: string;
  child_count?: number;
};

export type FileBrowseItem = FileAsset & {
  name?: string;
  web_url?: string;
  source?: "platform" | "sharepoint" | "onedrive";
};

export type FileBrowseResult = {
  source: "platform" | "sharepoint" | "onedrive";
  current_item_id: string;
  parent_item_id?: string | null;
  breadcrumbs: Array<{ id: string; name: string }>;
  folders: FileBrowseFolder[];
  files: FileBrowseItem[];
  folder_tree?: FileFolderNode[];
  mock?: boolean;
};

export type FileSource = {
  id: "platform" | "sharepoint" | "onedrive";
  label: string;
  configured: boolean;
  mock: boolean;
  outlook_connected?: boolean;
  oauth_available?: boolean;
};

export type ArticleTemplate = {
  id: string;
  title: string;
  content: string;
};

export type SearchResult = {
  type: "article" | "file" | "certificate";
  id: string;
  title: string;
  snippet: string;
  status?: string | null;
  folder?: string | null;
  updated_at: string;
  relevance?: number | null;
};

export type SearchResultType = SearchResult["type"];

export type SearchResponse = {
  query: string;
  results: SearchResult[];
  counts: Record<SearchResultType, number>;
  ai_available: boolean;
};

export type SearchAskResponse = {
  question: string;
  search_query: string;
  answer: string;
  mode: "ai" | "keyword";
  results: SearchResult[];
  counts: Record<SearchResultType, number>;
  suggested_queries: string[];
  ai_available: boolean;
};

export type Certificate = {
  id: string;
  name: string;
  category: "compliance" | "product" | "training" | "ssl";
  issuer: string;
  valid_from: string;
  valid_to: string;
  renewal_in_progress: boolean;
  renewal_approval_status?: string;
  renewal_review_comment?: string;
  status: "valid" | "expiring" | "expired" | "renewal";
  days_until_expiry: number;
  responsible_name: string;
  responsible_email: string;
  escalate_email?: string;
  parent_id?: string | null;
  parent_name?: string | null;
  children?: Array<{
    id: string;
    name: string;
    status: string;
    valid_to: string;
    days_until_expiry: number;
  }>;
  file_asset_id: string | null;
  file_name: string | null;
  notes: string;
  fingerprint?: string;
  external_source?: string;
  external_id?: string;
  created_by_id: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
};

export type ParsedSslCertificate = {
  name: string;
  issuer: string;
  valid_from: string;
  valid_to: string;
  fingerprint_sha256: string;
  serial_number: string;
  subject: string;
  sans: string[];
  is_lets_encrypt: boolean;
  category: "ssl";
};

export type CaSyncStatus = {
  ssl_file_import: boolean;
  letsencrypt_configured: boolean;
  letsencrypt_live_dir: string;
  key_vault_configured: boolean;
  key_vault_url: string;
  key_vault_mock: boolean;
};

export type CaSyncResult = {
  source: string;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
  mock?: boolean;
};

export type DashboardStats = {
  drafts: number;
  in_review: number;
  scheduled: number;
  published: number;
  files: number;
  certificates: number;
  renewals_pending: number;
  expiring_30: number;
  expiring_60: number;
  expiring_90: number;
  products?: number;
  products_published?: number;
};

export type Product = {
  id: string;
  name: string;
  slug: string;
  short_description: string;
  description: string;
  price_cents: number;
  currency: string;
  sku: string;
  is_published: boolean;
  sort_order: number;
  image_file_asset_id: string | null;
  image_name?: string | null;
  image_url?: string | null;
  stock_qty?: number;
  track_inventory?: boolean;
  vat_rate_bps?: number;
  created_by_id: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
};

export type ShopProduct = {
  id: string;
  name: string;
  slug: string;
  short_description: string;
  description: string;
  price_cents: number;
  currency: string;
  sku: string;
  image_url?: string | null;
  sort_order: number;
  vat_rate_bps?: number;
  track_inventory?: boolean;
  stock_available?: number | null;
  in_stock?: boolean;
};

export type ShopConfig = {
  brand_name: string;
  company_name?: string;
  tagline: string;
  contact_email: string;
  currency: string;
  hosts: string[];
  platform_url: string;
  shipping_cents?: number;
  free_shipping_from_cents?: number;
  stripe_enabled?: boolean;
  stripe_publishable_key?: string;
  invoice_enabled?: boolean;
  require_account_checkout?: boolean;
  co2_credits_per_euro?: number;
  return_window_days?: number;
  analytics_enabled?: boolean;
  bot_protection?: {
    enabled?: boolean;
    turnstile_site_key?: string;
    turnstile_required?: boolean;
  };
  bank?: { iban: string; bic: string; name: string; holder: string };
  legal?: { impressum: string; privacy: string; terms: string };
};

export type ShopMonitoringSummary = {
  days: number;
  views_today: number;
  views_7d: number;
  views_period: number;
  unique_visitors_today: number;
  unique_visitors_7d: number;
  unique_visitors_period: number;
  by_day: Array<{ day: string; count: number }>;
  top_paths: Array<{ path: string; count: number }>;
  top_ips?: Array<{ ip: string; count: number }>;
  recent: Array<{
    id: string;
    path: string;
    referrer: string;
    session_id: string;
    ip_address?: string;
    created_at?: string | null;
  }>;
};

export type ShopCustomer = {
  id: string;
  email: string;
  name: string;
  language: string;
  is_active: boolean;
  co2_credit_balance: number;
  created_at?: string | null;
  last_login_at?: string | null;
};

export type ShopCreditLedgerEntry = {
  id: string;
  order_id?: string | null;
  delta_credits: number;
  reason: string;
  note: string;
  created_at?: string | null;
};

export type ShopOrder = {
  id: string;
  order_number: string;
  access_token?: string;
  status: string;
  payment_method: string;
  currency: string;
  subtotal_cents: number;
  shipping_cents: number;
  vat_cents: number;
  total_cents: number;
  customer_id?: string | null;
  customer_email: string;
  customer_name: string;
  customer_phone?: string;
  company?: string;
  address_line1: string;
  address_line2?: string;
  postal_code: string;
  city: string;
  country: string;
  notes?: string;
  credits_earned?: number;
  shipping_carrier?: string;
  tracking_number?: string;
  tracking_url?: string;
  invoice_url?: string;
  paid_at?: string | null;
  fulfilled_at?: string | null;
  created_at?: string | null;
  items: Array<{
    id: string;
    product_id: string;
    product_name: string;
    product_sku: string;
    unit_price_cents: number;
    vat_rate_bps: number;
    quantity: number;
    line_total_cents: number;
  }>;
};

export type AnalyticsChannelStat = {
  channel: string;
  sent: number;
  failed: number;
  pending: number;
  total: number;
};

export type AnalyticsOverview = {
  generated_at: string;
  range_days: number;
  articles: {
    total: number;
    by_status: Record<string, number>;
  };
  certificates: {
    total: number;
    by_status: Record<string, number>;
    by_category: Record<string, number>;
    expiring_30: number;
    expiring_60: number;
    expiring_90: number;
    renewals_pending: number;
  };
  publications: {
    total: number;
    in_range: number;
    by_day: Array<{ date: string; count: number }>;
    deliveries: {
      total: number;
      by_status: Record<string, number>;
      by_channel: AnalyticsChannelStat[];
    };
    recent: Array<{
      id: string;
      title: string;
      published_by_name: string;
      created_at?: string | null;
      channels_ok: number;
      channels_failed: number;
      channels_total: number;
    }>;
  };
  files: { total: number };
  activity: {
    top_authors: Array<{ author_name: string; article_count: number }>;
    audit_actions_in_range: number;
  };
};

export type WorkflowPending = {
  articles_in_review: Array<{
    id: string;
    title: string;
    status: string;
    author_name: string;
    updated_at: string;
  }>;
  articles_scheduled: Array<{
    id: string;
    title: string;
    status: string;
    scheduled_publish_at?: string | null;
    updated_at: string;
  }>;
  certificate_renewals_pending: Array<{
    id: string;
    name: string;
    renewal_approval_status: string;
    responsible_name: string;
    updated_at: string;
  }>;
};

export type AuditEntry = {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_id: string;
  actor_name: string;
  actor_email: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type PlatformInfo = {
  deployment_region: string;
  storage_backend: string;
  oss_configured: boolean;
  sync_configured: boolean;
  sync_peer_region: string;
};

export type SyncStatus = {
  region: string;
  peer_region: string;
  peer_url: string | null;
  sync_enabled: boolean;
  storage_backend: string;
  article_count: number;
  certificate_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_message: string | null;
};

type ApiError = {
  error: string;
  code: string;
};

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(path, {
      credentials: "include",
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      let message = "Request failed";
      if (response.status === 502 || response.status === 503) {
        message = "Server temporarily unavailable";
      }
      try {
        const payload = (await response.json()) as ApiError;
        message = payload.error ?? message;
      } catch {
        if (response.status >= 500) {
          message = "Server temporarily unavailable";
        }
      }
      throw new Error(message);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const payload = await request<{ user: User }>("/api/auth/me");
    return payload.user;
  } catch {
    return null;
  }
}

export async function updateUserLanguage(language: string): Promise<User> {
  const payload = await request<{ user: User }>("/api/user/language", {
    method: "PATCH",
    body: JSON.stringify({ language }),
  });
  return payload.user;
}

export async function logout(): Promise<void> {
  await request<void>("/api/auth/logout", { method: "POST" });
}

export async function loginWithPassword(email: string, password: string): Promise<User> {
  const payload = await request<{ user: User }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return payload.user;
}

export async function fetchInvite(token: string): Promise<PublicInvite> {
  const payload = await request<{ invite: PublicInvite }>(`/api/auth/invite/${encodeURIComponent(token)}`);
  return payload.invite;
}

export async function acceptInvite(token: string, name: string, password: string): Promise<User> {
  const payload = await request<{ user: User }>("/api/auth/accept-invite", {
    method: "POST",
    body: JSON.stringify({ token, name, password }),
  });
  return payload.user;
}

export function loginUrl(language: string): string {
  return `/api/auth/login?lang=${encodeURIComponent(language)}`;
}

export type AuthConfig = {
  password_auth: boolean;
  microsoft_auth: boolean;
  mock_auth: boolean;
};

export async function fetchAuthConfig(): Promise<AuthConfig> {
  const payload = await request<AuthConfig & { status: string }>("/api/health");
  return {
    password_auth: payload.password_auth,
    microsoft_auth: payload.microsoft_auth,
    mock_auth: payload.mock_auth,
  };
}

export type DashboardHome = {
  greeting_name: string;
  my_drafts: Array<{
    id: string;
    title: string;
    status: string;
    scheduled_publish_at?: string | null;
    updated_at?: string | null;
    author_name?: string;
  }>;
  my_in_review: Array<{
    id: string;
    title: string;
    status: string;
    updated_at?: string | null;
  }>;
  my_approvals: Array<{
    kind: string;
    id: string;
    title?: string;
    name?: string;
    status?: string;
    valid_to?: string;
    days_until_expiry?: number;
  }>;
  my_expiring_certificates: Array<{
    id: string;
    name: string;
    status: string;
    valid_to: string;
    days_until_expiry: number;
  }>;
  upcoming_scheduled: Array<{
    id: string;
    title: string;
    scheduled_publish_at?: string | null;
  }>;
  recent_publications: Array<{
    id: string;
    title: string;
    resource_type: string;
    resource_id: string;
    published_by_name: string;
    created_at?: string | null;
  }>;
  counts: {
    my_drafts: number;
    my_in_review: number;
    my_approvals: number;
    my_expiring: number;
    upcoming_scheduled: number;
  };
};

export type CalendarEvent = {
  id: string;
  type: "scheduled_publish" | "publication" | "certificate_reminder" | "certificate_expiry" | "outlook_event" | string;
  title: string;
  date: string;
  datetime?: string | null;
  resource_type: string;
  resource_id: string;
  status?: string;
  external_url?: string;
  location?: string;
};

export type PublishCalendar = {
  range: { start: string; end: string };
  events: CalendarEvent[];
  by_date: Record<string, CalendarEvent[]>;
};

export type OutlookStatus = {
  connected: boolean;
  account: string;
  connected_at?: string | null;
  calendar_enabled?: boolean;
  mail_enabled?: boolean;
  oauth_available: boolean;
};

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const payload = await request<{ stats: DashboardStats }>("/api/dashboard/stats");
  return payload.stats;
}

export async function fetchAnalyticsOverview(days = 90): Promise<AnalyticsOverview> {
  const params = new URLSearchParams({ days: String(days) });
  const payload = await request<{ overview: AnalyticsOverview }>(`/api/analytics/overview?${params}`);
  return payload.overview;
}

export async function fetchDashboardHome(): Promise<DashboardHome> {
  const payload = await request<{ home: DashboardHome }>("/api/dashboard/home");
  return payload.home;
}

export async function fetchPublishCalendar(
  daysAhead = 90,
  daysBack = 14,
): Promise<{ calendar: PublishCalendar; outlook: OutlookStatus }> {
  const params = new URLSearchParams({
    days_ahead: String(daysAhead),
    days_back: String(daysBack),
  });
  return request<{ calendar: PublishCalendar; outlook: OutlookStatus }>(`/api/dashboard/calendar?${params}`);
}

export async function fetchOutlookStatus(): Promise<OutlookStatus> {
  return request<OutlookStatus>("/api/integrations/outlook/status");
}

export async function disconnectOutlook(): Promise<void> {
  await request<void>("/api/integrations/outlook", { method: "DELETE" });
}

export function outlookConnectUrl(): string {
  return "/api/integrations/outlook/connect";
}

export async function fetchPlatformInfo(): Promise<PlatformInfo> {
  const payload = await request<PlatformInfo & { status: string }>("/api/health");
  return {
    deployment_region: payload.deployment_region,
    storage_backend: payload.storage_backend,
    oss_configured: payload.oss_configured,
    sync_configured: payload.sync_configured,
    sync_peer_region: payload.sync_peer_region,
  };
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  return request<SyncStatus>("/api/sync/status");
}

export async function runRegionSync(): Promise<unknown> {
  return request("/api/sync/run", { method: "POST" });
}

export async function fetchArticles(q?: string, status?: string): Promise<Article[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  const query = params.toString();
  const payload = await request<{ articles: Article[] }>(`/api/articles${query ? `?${query}` : ""}`);
  return payload.articles;
}

export async function fetchArticle(id: string): Promise<Article> {
  const payload = await request<{ article: Article }>(`/api/articles/${id}`);
  return payload.article;
}

export async function fetchArticleTemplates(): Promise<ArticleTemplate[]> {
  const payload = await request<{ templates: ArticleTemplate[] }>("/api/articles/templates");
  return payload.templates;
}

export async function createArticle(data: Partial<Article> & { title: string; content: string }): Promise<Article> {
  const payload = await request<{ article: Article }>("/api/articles", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.article;
}

export async function updateArticle(id: string, data: Partial<Article>): Promise<Article> {
  const payload = await request<{ article: Article }>(`/api/articles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.article;
}

export async function deleteArticle(id: string): Promise<void> {
  await request<void>(`/api/articles/${id}`, { method: "DELETE" });
}

export async function fetchFiles(
  q?: string,
  folder?: string,
  folderId?: string,
): Promise<{ files: FileAsset[]; folders: string[]; folder_tree?: FileFolderNode[] }> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (folder) params.set("folder", folder);
  if (folderId) params.set("folder_id", folderId);
  const query = params.toString();
  return request<{ files: FileAsset[]; folders: string[]; folder_tree?: FileFolderNode[] }>(
    `/api/files${query ? `?${query}` : ""}`,
  );
}

export async function fetchFileSources(): Promise<FileSource[]> {
  const payload = await request<{ sources: FileSource[] }>("/api/files/sources");
  return payload.sources;
}

export async function fetchFileFolderTree(): Promise<FileFolderNode[]> {
  const payload = await request<{ folders: FileFolderNode[] }>("/api/files/folders/tree");
  return payload.folders;
}

export async function browseFiles(
  source: FileSource["id"],
  itemId?: string,
  q?: string,
): Promise<FileBrowseResult> {
  const params = new URLSearchParams({ source });
  if (itemId) params.set("item_id", itemId);
  if (q) params.set("q", q);
  return request<FileBrowseResult>(`/api/files/browse?${params.toString()}`);
}

export async function uploadFile(file: File, folder: string, folderId?: string): Promise<FileAsset> {
  const body = new FormData();
  body.append("upload", file);
  body.append("folder", folder);
  if (folderId) body.append("folder_id", folderId);
  const payload = await request<{ file: FileAsset }>("/api/files/upload", {
    method: "POST",
    body,
  });
  return payload.file;
}

export async function importFileFromSharePoint(
  itemId: string,
  folder = "certificates",
): Promise<{ file: FileAsset; source: { provider: string; item_id: string; web_url: string; mock: boolean } }> {
  return request("/api/files/import-from-sharepoint", {
    method: "POST",
    body: JSON.stringify({ item_id: itemId, folder }),
  });
}

export async function deleteFile(id: string): Promise<void> {
  await request<void>(`/api/files/${id}`, { method: "DELETE" });
}

export function fileDownloadUrl(id: string): string {
  return `/api/files/${id}/download`;
}

export type OfficeSession = {
  source: "platform" | "sharepoint" | "onedrive";
  item_id: string;
  name: string;
  embed_url: string;
  edit_url: string;
  can_edit: boolean;
  mock?: boolean;
  expires_at?: string | null;
  preview_url?: string;
};

export async function fetchOfficeSession(
  source: FileSource["id"],
  itemId: string,
): Promise<OfficeSession> {
  const params = new URLSearchParams({ source, item_id: itemId });
  const payload = await request<{ session: OfficeSession }>(`/api/files/office/session?${params}`);
  return payload.session;
}

export async function searchContent(q: string, type?: SearchResultType): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (type) params.set("type", type);
  return request<SearchResponse>(`/api/search?${params.toString()}`);
}

export async function askSearch(
  question: string,
  language?: string,
  type?: SearchResultType,
): Promise<SearchAskResponse> {
  return request<SearchAskResponse>(
    "/api/search/ask",
    {
      method: "POST",
      body: JSON.stringify({ question, language, type: type || null }),
    },
    45000,
  );
}

export async function fetchSearchSuggestions(): Promise<{
  suggestions: string[];
  ai_available: boolean;
  assistant_name?: string;
}> {
  return request<{ suggestions: string[]; ai_available: boolean; assistant_name?: string }>(
    "/api/search/suggestions",
  );
}

export type AiStatus = {
  available: boolean;
  features: string[];
  assistant_name: string;
};

export type AiTranslation = {
  title: string;
  content: string;
  target_language: string;
};

export async function fetchAiStatus(): Promise<AiStatus> {
  return request<AiStatus>("/api/ai/status");
}

export async function translateArticleContent(payload: {
  title: string;
  content: string;
  target_language: "de" | "en" | "zh-CN";
  source_language?: "de" | "en" | "zh-CN";
}): Promise<AiTranslation> {
  const response = await request<{ translation: AiTranslation }>(
    "/api/ai/translate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    60000,
  );
  return response.translation;
}

export async function summarizeArticleContent(payload: {
  title: string;
  content: string;
  language?: "de" | "en" | "zh-CN";
}): Promise<string> {
  const response = await request<{ summary: string }>(
    "/api/ai/summarize",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    45000,
  );
  return response.summary;
}

export async function fetchCertificates(
  q?: string,
  category?: string,
  status?: string,
): Promise<Certificate[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  if (status) params.set("status", status);
  const query = params.toString();
  const payload = await request<{ certificates: Certificate[] }>(
    `/api/certificates${query ? `?${query}` : ""}`,
  );
  return payload.certificates;
}

export async function fetchCertificate(id: string): Promise<Certificate> {
  const payload = await request<{ certificate: Certificate }>(`/api/certificates/${id}`);
  return payload.certificate;
}

export async function createCertificate(
  data: {
    name: string;
    category: Certificate["category"];
    issuer: string;
    valid_from: string;
    valid_to: string;
    renewal_in_progress: boolean;
    responsible_name: string;
    responsible_email: string;
    escalate_email?: string;
    parent_id?: string | null;
    file_asset_id: string | null;
    notes: string;
  },
): Promise<Certificate> {
  const payload = await request<{ certificate: Certificate }>("/api/certificates", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.certificate;
}

export async function importCertificateFromSharePoint(
  data: {
    item_id: string;
    name?: string;
    category?: Certificate["category"];
    issuer?: string;
    valid_from?: string;
    valid_to?: string;
    responsible_name?: string;
    responsible_email?: string;
    escalate_email?: string;
    parent_id?: string | null;
    notes?: string;
  },
): Promise<Certificate> {
  const payload = await request<{ certificate: Certificate }>("/api/certificates/import-from-sharepoint", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.certificate;
}

export async function parseSslCertificateFile(file: File): Promise<ParsedSslCertificate> {
  const body = new FormData();
  body.append("upload", file);
  const payload = await request<{ parsed: ParsedSslCertificate }>("/api/certificates/parse-ssl", {
    method: "POST",
    body,
  });
  return payload.parsed;
}

export async function parseSslCertificateAsset(fileAssetId: string): Promise<ParsedSslCertificate> {
  const params = new URLSearchParams({ file_asset_id: fileAssetId });
  const payload = await request<{ parsed: ParsedSslCertificate }>(`/api/certificates/parse-ssl?${params}`, {
    method: "POST",
  });
  return payload.parsed;
}

export async function importSslCertificateFile(file: File): Promise<{
  certificate: Certificate;
  created: boolean;
  parsed: ParsedSslCertificate;
}> {
  const body = new FormData();
  body.append("upload", file);
  return request("/api/certificates/import-ssl", {
    method: "POST",
    body,
  });
}

export async function fetchCaSyncStatus(): Promise<CaSyncStatus> {
  return request<CaSyncStatus>("/api/certificates/ca-sync/status");
}

export async function syncCertificatesFromLetsEncrypt(): Promise<CaSyncResult> {
  return request<CaSyncResult>("/api/certificates/ca-sync/letsencrypt", { method: "POST" });
}

export async function syncCertificatesFromKeyVault(): Promise<CaSyncResult> {
  return request<CaSyncResult>("/api/certificates/ca-sync/key-vault", { method: "POST" });
}

export async function updateCertificate(id: string, data: Partial<Certificate>): Promise<Certificate> {
  const payload = await request<{ certificate: Certificate }>(`/api/certificates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.certificate;
}

export async function deleteCertificate(id: string): Promise<void> {
  await request<void>(`/api/certificates/${id}`, { method: "DELETE" });
}

export async function fetchProducts(q?: string, published?: boolean): Promise<Product[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (published !== undefined) params.set("published", String(published));
  const query = params.toString();
  const payload = await request<{ products: Product[] }>(`/api/products${query ? `?${query}` : ""}`);
  return payload.products;
}

export async function fetchProduct(id: string): Promise<Product> {
  const payload = await request<{ product: Product }>(`/api/products/${id}`);
  return payload.product;
}

export async function createProduct(data: {
  name: string;
  slug?: string;
  short_description?: string;
  description?: string;
  price_cents: number;
  currency?: string;
  sku?: string;
  is_published?: boolean;
  sort_order?: number;
  image_file_asset_id?: string | null;
  stock_qty?: number;
  track_inventory?: boolean;
  vat_rate_bps?: number;
}): Promise<Product> {
  const payload = await request<{ product: Product }>("/api/products", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.product;
}

export async function updateProduct(id: string, data: Partial<Product>): Promise<Product> {
  const payload = await request<{ product: Product }>(`/api/products/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.product;
}

export async function deleteProduct(id: string): Promise<void> {
  await request<void>(`/api/products/${id}`, { method: "DELETE" });
}

export async function fetchShopConfig(): Promise<ShopConfig> {
  return request<ShopConfig>("/api/shop/config");
}

export async function fetchShopProducts(): Promise<ShopProduct[]> {
  const payload = await request<{ products: ShopProduct[] }>("/api/shop/products");
  return payload.products;
}

export async function fetchShopProduct(slug: string): Promise<ShopProduct> {
  const payload = await request<{ product: ShopProduct }>(`/api/shop/products/${encodeURIComponent(slug)}`);
  return payload.product;
}

export async function checkoutShop(data: {
  items: Array<{ product_id: string; quantity: number }>;
  customer: {
    email: string;
    name: string;
    phone?: string;
    company?: string;
    address_line1: string;
    address_line2?: string;
    postal_code: string;
    city: string;
    country: string;
  };
  payment_method: "stripe" | "invoice";
  notes?: string;
  website?: string;
  turnstile_token?: string;
}): Promise<{ order: ShopOrder; checkout_url: string | null }> {
  return request("/api/shop/checkout", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function trackShopPageView(data: {
  path: string;
  referrer?: string;
  session_id: string;
  website?: string;
}): Promise<void> {
  try {
    await request<{ ok: boolean }>("/api/shop/analytics/pageview", {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch {
    // Non-blocking analytics
  }
}

export async function fetchShopMonitoringSummary(days = 30): Promise<ShopMonitoringSummary> {
  const params = new URLSearchParams({ days: String(days) });
  return request<ShopMonitoringSummary>(`/api/shop/monitoring/summary?${params}`);
}

export type ReputationDeletion = {
  id: string;
  mention_id: string;
  status: string;
  reason: string;
  notes: string;
  letter: string;
  publisher_email: string;
  requested_by_name?: string;
  created_at?: string | null;
};

export type ReputationMention = {
  id: string;
  url: string;
  title: string;
  snippet: string;
  excerpt: string;
  source_host: string;
  query: string;
  channel: string;
  sentiment: "negative" | "neutral" | "positive" | string;
  sentiment_score: number;
  sentiment_reasons: string;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  deletion?: ReputationDeletion | null;
};

export type ReputationSummary = {
  total: number;
  negative: number;
  positive: number;
  neutral: number;
  open_deletion_requests: number;
  last_run?: {
    id: string;
    status: string;
    found: number;
    created: number;
    updated: number;
    negative: number;
    error?: string;
    started_at?: string | null;
    finished_at?: string | null;
  } | null;
};

export type ReputationCrawlRun = {
  id: string;
  status: string;
  found: number;
  created: number;
  updated: number;
  negative: number;
  error?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export async function fetchReputationSummary(): Promise<ReputationSummary> {
  return request<ReputationSummary>("/api/reputation/summary");
}

export async function fetchReputationMentions(filters?: {
  sentiment?: string;
  q?: string;
  seen_from?: string;
  seen_to?: string;
}): Promise<ReputationMention[]> {
  const params = new URLSearchParams();
  if (filters?.sentiment) params.set("sentiment", filters.sentiment);
  if (filters?.q) params.set("q", filters.q);
  if (filters?.seen_from) params.set("seen_from", filters.seen_from);
  if (filters?.seen_to) params.set("seen_to", filters.seen_to);
  const query = params.toString();
  const payload = await request<{ mentions: ReputationMention[] }>(
    `/api/reputation/mentions${query ? `?${query}` : ""}`,
  );
  return payload.mentions;
}

export async function runReputationCrawl(): Promise<ReputationCrawlRun> {
  const payload = await request<{ run: ReputationCrawlRun }>("/api/reputation/crawl", { method: "POST" });
  return payload.run;
}

export async function requestReputationDeletion(
  mentionId: string,
  data: { reason: string; notes?: string; publisher_email?: string },
): Promise<{ request: ReputationDeletion; mention: ReputationMention }> {
  return request(`/api/reputation/mentions/${mentionId}/deletion-requests`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function closeReputationDeletion(requestId: string): Promise<{ request: ReputationDeletion }> {
  return request(`/api/reputation/deletion-requests/${requestId}/close`, { method: "PATCH" });
}

export async function fetchShopOrder(orderNumber: string, token: string): Promise<ShopOrder> {
  const params = new URLSearchParams({ token });
  const payload = await request<{ order: ShopOrder }>(
    `/api/shop/orders/${encodeURIComponent(orderNumber)}?${params}`,
  );
  return payload.order;
}

export async function confirmShopOrder(
  orderNumber: string,
  token: string,
  sessionId: string,
): Promise<ShopOrder> {
  const params = new URLSearchParams({ token, session_id: sessionId });
  const payload = await request<{ order: ShopOrder }>(
    `/api/shop/orders/${encodeURIComponent(orderNumber)}/confirm?${params}`,
    { method: "POST" },
  );
  return payload.order;
}

export async function registerShopCustomer(data: {
  email: string;
  name: string;
  password: string;
  language?: string;
  website?: string;
  turnstile_token?: string;
}): Promise<ShopCustomer> {
  const payload = await request<{ customer: ShopCustomer }>("/api/shop/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.customer;
}

export async function loginShopCustomer(data: {
  email: string;
  password: string;
  website?: string;
  turnstile_token?: string;
}): Promise<ShopCustomer> {
  const payload = await request<{ customer: ShopCustomer }>("/api/shop/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.customer;
}

export async function logoutShopCustomer(): Promise<void> {
  await request<{ ok: boolean }>("/api/shop/auth/logout", { method: "POST" });
}

export async function fetchShopCustomerMe(): Promise<ShopCustomer | null> {
  try {
    const payload = await request<{ customer: ShopCustomer }>("/api/shop/auth/me");
    return payload.customer;
  } catch {
    return null;
  }
}

export async function fetchShopMyCredits(): Promise<{ balance: number; ledger: ShopCreditLedgerEntry[] }> {
  return request("/api/shop/auth/me/credits");
}

export async function fetchShopMyOrders(): Promise<ShopOrder[]> {
  const payload = await request<{ orders: ShopOrder[] }>("/api/shop/auth/me/orders");
  return payload.orders;
}

export type ShopReturn = {
  id: string;
  return_number: string;
  order_id: string;
  customer_id?: string | null;
  status: "requested" | "approved" | "rejected" | "completed" | string;
  reason: string;
  customer_note: string;
  admin_note: string;
  refund_method: string;
  credits_reversed: number;
  inventory_restored: boolean;
  requested_at?: string | null;
  resolved_at?: string | null;
  completed_at?: string | null;
  resolved_by_name?: string;
  order_number?: string;
  order_status?: string;
  order_total_cents?: number;
  order_currency?: string;
  customer_email?: string;
  customer_name?: string;
  credits_earned?: number;
  created_at?: string | null;
};

export async function fetchShopMyReturns(): Promise<ShopReturn[]> {
  const payload = await request<{ returns: ShopReturn[] }>("/api/shop/auth/me/returns");
  return payload.returns;
}

export async function requestShopReturn(
  orderId: string,
  data: { reason: string; customer_note?: string },
): Promise<ShopReturn> {
  const payload = await request<{ return: ShopReturn }>(`/api/shop/auth/me/orders/${orderId}/returns`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.return;
}

export async function fetchAdminShopReturns(status?: string): Promise<ShopReturn[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const query = params.toString();
  const payload = await request<{ returns: ShopReturn[] }>(`/api/shop-returns${query ? `?${query}` : ""}`);
  return payload.returns;
}

export async function resolveAdminShopReturn(
  returnId: string,
  data: { status: "approved" | "rejected" | "completed"; admin_note?: string },
): Promise<ShopReturn> {
  const payload = await request<{ return: ShopReturn }>(`/api/shop-returns/${returnId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.return;
}

export async function fetchShopCustomersAdmin(): Promise<ShopCustomer[]> {
  const payload = await request<{ customers: ShopCustomer[] }>("/api/shop-customers");
  return payload.customers;
}

export async function fetchShopCustomerAdmin(customerId: string): Promise<{
  customer: ShopCustomer;
  ledger: ShopCreditLedgerEntry[];
  orders: ShopOrder[];
}> {
  return request(`/api/shop-customers/${customerId}`);
}

export async function updateShopCustomerActive(customerId: string, isActive: boolean): Promise<ShopCustomer> {
  const payload = await request<{ customer: ShopCustomer }>(`/api/shop-customers/${customerId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
  return payload.customer;
}

export async function adjustShopCustomerCredits(
  customerId: string,
  delta: number,
  note = "",
): Promise<ShopCustomer> {
  const payload = await request<{ customer: ShopCustomer }>(`/api/shop-customers/${customerId}/credits`, {
    method: "POST",
    body: JSON.stringify({ delta, note }),
  });
  return payload.customer;
}

export async function fetchAdminOrders(status?: string): Promise<ShopOrder[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const query = params.toString();
  const payload = await request<{ orders: ShopOrder[] }>(`/api/orders${query ? `?${query}` : ""}`);
  return payload.orders;
}

export async function updateAdminOrderStatus(
  orderId: string,
  status: string,
  shipping?: {
    shipping_carrier?: string;
    tracking_number?: string;
    tracking_url?: string;
  },
): Promise<ShopOrder> {
  const payload = await request<{ order: ShopOrder }>(`/api/orders/${orderId}`, {
    method: "PATCH",
    body: JSON.stringify({
      status,
      shipping_carrier: shipping?.shipping_carrier || "",
      tracking_number: shipping?.tracking_number || "",
      tracking_url: shipping?.tracking_url || "",
    }),
  });
  return payload.order;
}

export function adminOrderInvoiceUrl(orderId: string): string {
  return `/api/orders/${orderId}/invoice.pdf`;
}

export function shopAccountOrderInvoiceUrl(orderId: string): string {
  return `/api/shop/auth/me/orders/${orderId}/invoice.pdf`;
}

export function shopPublicOrderInvoiceUrl(orderNumber: string, token: string): string {
  return `/api/shop/orders/${encodeURIComponent(orderNumber)}/invoice.pdf?token=${encodeURIComponent(token)}`;
}

export function formatMoney(cents: number, currency = "EUR", locale = "de-DE"): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(cents / 100);
}

export function certificatesExportUrl(): string {
  return "/api/certificates/export";
}

export function certificatesAuditExportUrl(): string {
  return "/api/certificates/audit-export";
}

export type CertificateChainNode = {
  id: string;
  name: string;
  category: string;
  status: Certificate["status"] | string;
  valid_to: string;
  days_until_expiry: number;
  parent_id?: string | null;
  children: CertificateChainNode[];
};

export async function fetchCertificateChains(): Promise<CertificateChainNode[]> {
  const payload = await request<{ chains: CertificateChainNode[] }>("/api/certificates/chains");
  return payload.chains;
}

export async function fetchUsers(): Promise<User[]> {
  const payload = await request<{ users: User[] }>("/api/user/users");
  return payload.users;
}

export type M365LicenseRef = { sku_id: string; name: string };

export type M365DirectoryUser = {
  id: string;
  display_name: string;
  user_principal_name: string;
  mail: string;
  job_title: string;
  department: string;
  account_enabled: boolean;
  user_type: string;
  licenses: string[];
  license_skus: M365LicenseRef[];
  usage_location: string;
  created_at?: string | null;
};

export type M365Group = { id: string; display_name: string };

export type M365License = {
  sku_id: string;
  name: string;
  total: number;
  consumed: number;
  available: number;
};

export type M365DirectoryStatus = {
  mock: boolean;
  graph_configured: boolean;
  permissions: string[];
  assistant_name?: string;
};

export async function fetchM365Status(): Promise<M365DirectoryStatus> {
  return request<M365DirectoryStatus>("/api/m365/status");
}

export async function fetchM365Users(query = ""): Promise<{ users: M365DirectoryUser[]; mock: boolean }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<{ users: M365DirectoryUser[]; mock: boolean }>(`/api/m365/users${suffix}`);
}

export async function createM365User(data: {
  display_name: string;
  user_principal_name: string;
  password?: string;
  job_title?: string;
  department?: string;
  usage_location?: string;
}): Promise<{ user: M365DirectoryUser; temporary_password: string }> {
  return request<{ user: M365DirectoryUser; temporary_password: string }>("/api/m365/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function setM365UserEnabled(
  userId: string,
  accountEnabled: boolean,
): Promise<M365DirectoryUser> {
  const payload = await request<{ user: M365DirectoryUser }>(`/api/m365/users/${encodeURIComponent(userId)}/enabled`, {
    method: "PATCH",
    body: JSON.stringify({ account_enabled: accountEnabled }),
  });
  return payload.user;
}

export async function resetM365Password(
  userId: string,
): Promise<{ user: M365DirectoryUser; temporary_password: string }> {
  return request<{ user: M365DirectoryUser; temporary_password: string }>(
    `/api/m365/users/${encodeURIComponent(userId)}/reset-password`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function fetchM365Groups(query = ""): Promise<M365Group[]> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const payload = await request<{ groups: M365Group[] }>(`/api/m365/groups${suffix}`);
  return payload.groups;
}

export async function fetchM365Licenses(): Promise<M365License[]> {
  const payload = await request<{ licenses: M365License[] }>("/api/m365/licenses");
  return payload.licenses;
}

export async function assignM365License(userId: string, skuId: string): Promise<M365DirectoryUser> {
  const payload = await request<{ user: M365DirectoryUser }>(
    `/api/m365/users/${encodeURIComponent(userId)}/licenses`,
    { method: "POST", body: JSON.stringify({ sku_id: skuId }) },
  );
  return payload.user;
}

export async function removeM365License(userId: string, skuId: string): Promise<M365DirectoryUser> {
  const payload = await request<{ user: M365DirectoryUser }>(
    `/api/m365/users/${encodeURIComponent(userId)}/licenses/${encodeURIComponent(skuId)}`,
    { method: "DELETE" },
  );
  return payload.user;
}

export async function askM365Directory(
  question: string,
  language?: string,
): Promise<{
  question: string;
  answer: string;
  action: string;
  users: M365DirectoryUser[];
  temporary_password: string;
  assistant_name?: string;
}> {
  return request(
    "/api/m365/ask",
    {
      method: "POST",
      body: JSON.stringify({ question, language }),
    },
    45000,
  );
}

export async function createUser(data: {
  email: string;
  name: string;
  password: string;
  role: User["role"];
  department_id?: string | null;
}): Promise<User> {
  const payload = await request<{ user: User }>("/api/user/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.user;
}

export async function updateUserPassword(userId: string, password: string): Promise<User> {
  const payload = await request<{ user: User }>(`/api/user/users/${userId}/password`, {
    method: "PATCH",
    body: JSON.stringify({ password }),
  });
  return payload.user;
}

export async function updateUserRole(userId: string, role: User["role"]): Promise<User> {
  const payload = await request<{ user: User }>(`/api/user/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
  return payload.user;
}

export async function updateUserActive(userId: string, isActive: boolean): Promise<User> {
  const payload = await request<{ user: User }>(`/api/user/users/${userId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
  return payload.user;
}

export async function updateUserShopAccess(userId: string, canManageShopFlag: boolean): Promise<User> {
  const payload = await request<{ user: User }>(`/api/user/users/${userId}/shop-access`, {
    method: "PATCH",
    body: JSON.stringify({ can_manage_shop: canManageShopFlag }),
  });
  return payload.user;
}

export async function updateUserDepartment(userId: string, departmentId: string | null): Promise<User> {
  const payload = await request<{ user: User }>(`/api/user/users/${userId}/department`, {
    method: "PATCH",
    body: JSON.stringify({ department_id: departmentId }),
  });
  return payload.user;
}

export async function fetchDepartments(includeInactive = false): Promise<Department[]> {
  const query = includeInactive ? "?include_inactive=true" : "";
  const payload = await request<{ departments: Department[] }>(`/api/departments${query}`);
  return payload.departments;
}

export async function createDepartment(data: {
  name: string;
  code: string;
  sort_order?: number;
}): Promise<Department> {
  const payload = await request<{ department: Department }>("/api/departments", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.department;
}

export async function updateDepartment(
  departmentId: string,
  data: Partial<Pick<Department, "name" | "code" | "is_active" | "sort_order">>,
): Promise<Department> {
  const payload = await request<{ department: Department }>(`/api/departments/${departmentId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.department;
}

export async function deleteDepartment(departmentId: string): Promise<void> {
  await request<void>(`/api/departments/${departmentId}`, { method: "DELETE" });
}

export async function fetchGroupMappings(): Promise<EntraGroupMapping[]> {
  const payload = await request<{ mappings: EntraGroupMapping[] }>("/api/user/group-mappings");
  return payload.mappings;
}

export async function createGroupMapping(data: {
  entra_group_id: string;
  entra_group_name: string;
  role: User["role"];
}): Promise<EntraGroupMapping> {
  const payload = await request<{ mapping: EntraGroupMapping }>("/api/user/group-mappings", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.mapping;
}

export async function deleteGroupMapping(mappingId: string): Promise<void> {
  await request<void>(`/api/user/group-mappings/${mappingId}`, { method: "DELETE" });
}

export async function fetchInvites(): Promise<UserInvite[]> {
  const payload = await request<{ invites: UserInvite[] }>("/api/user/invites");
  return payload.invites;
}

export async function createInvite(data: {
  email: string;
  role: User["role"];
  department_id?: string | null;
}): Promise<UserInvite> {
  const payload = await request<{ invite: UserInvite }>("/api/user/invites", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return payload.invite;
}

export async function resendInvite(inviteId: string): Promise<UserInvite> {
  const payload = await request<{ invite: UserInvite }>(`/api/user/invites/${inviteId}/resend`, {
    method: "POST",
  });
  return payload.invite;
}

export async function revokeInvite(inviteId: string): Promise<void> {
  await request<void>(`/api/user/invites/${inviteId}`, { method: "DELETE" });
}

export type PublishChannel = {
  channel: "teams" | "outlook" | "notion";
  enabled: boolean;
  configured: boolean;
  available: boolean;
};

export type PublicationDelivery = {
  id: string;
  channel: PublishChannel["channel"];
  status: "pending" | "sent" | "failed";
  error_message?: string | null;
  external_id?: string | null;
  external_url?: string | null;
  attempt_count: number;
  updated_at: string;
};

export type Publication = {
  id: string;
  resource_type: string;
  resource_id: string;
  title: string;
  summary: string;
  published_by_id: string;
  published_by_name: string;
  created_at: string;
  deliveries: PublicationDelivery[];
};

export type PublishSettings = {
  teams_enabled: boolean;
  teams_team_id: string;
  teams_channel_id: string;
  outlook_enabled: boolean;
  outlook_sender_id: string;
  notion_enabled: boolean;
  notion_database_id: string;
  notion_configured: boolean;
  graph_configured: boolean;
  publish_mock_mode: boolean;
};

export async function fetchPublishChannels(): Promise<PublishChannel[]> {
  const payload = await request<{ channels: PublishChannel[] }>("/api/publish/channels");
  return payload.channels;
}

export async function fetchPublishSettings(): Promise<PublishSettings> {
  const payload = await request<{ settings: PublishSettings }>("/api/publish/settings");
  return payload.settings;
}

export async function updatePublishSettings(data: PublishSettings): Promise<PublishSettings> {
  const payload = await request<{ settings: PublishSettings }>("/api/publish/settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return payload.settings;
}

export async function fetchPublishHistory(resourceId?: string): Promise<Publication[]> {
  const query = resourceId ? `?resource_id=${encodeURIComponent(resourceId)}` : "";
  const payload = await request<{ publications: Publication[] }>(`/api/publish/history${query}`);
  return payload.publications;
}

export async function publishArticle(
  articleId: string,
  channels: PublishChannel["channel"][],
): Promise<Publication> {
  const payload = await request<{ publication: Publication }>(`/api/publish/articles/${articleId}`, {
    method: "POST",
    body: JSON.stringify({ channels }),
  });
  return payload.publication;
}

export async function retryPublicationDelivery(deliveryId: string): Promise<PublicationDelivery> {
  const payload = await request<{ delivery: PublicationDelivery }>(
    `/api/publish/deliveries/${deliveryId}/retry`,
    { method: "POST" },
  );
  return payload.delivery;
}

export async function runCertificateReminders(): Promise<{ reminders_sent: number; items: unknown[] }> {
  return request<{ reminders_sent: number; items: unknown[] }>("/api/publish/certificate-reminders", {
    method: "POST",
  });
}

export type IntegrationProviderStatus = {
  connected: boolean;
  account: string;
  connected_at?: string | null;
  oauth_available: boolean;
};

export type IntegrationStatus = {
  microsoft: IntegrationProviderStatus;
  notion: IntegrationProviderStatus;
};

export type IntegrationPickerItem = {
  id: string;
  name: string;
};

export async function fetchIntegrationStatus(): Promise<IntegrationStatus> {
  return request<IntegrationStatus>("/api/integrations/status");
}

export async function fetchMicrosoftTeams(): Promise<IntegrationPickerItem[]> {
  const payload = await request<{ teams: IntegrationPickerItem[] }>("/api/integrations/microsoft/teams");
  return payload.teams;
}

export async function fetchMicrosoftChannels(teamId: string): Promise<IntegrationPickerItem[]> {
  const payload = await request<{ channels: IntegrationPickerItem[] }>(
    `/api/integrations/microsoft/teams/${encodeURIComponent(teamId)}/channels`,
  );
  return payload.channels;
}

export async function fetchNotionDatabases(): Promise<IntegrationPickerItem[]> {
  const payload = await request<{ databases: IntegrationPickerItem[] }>("/api/integrations/notion/databases");
  return payload.databases;
}

export async function disconnectIntegration(provider: "microsoft" | "notion"): Promise<void> {
  await request<void>(`/api/integrations/${provider}`, { method: "DELETE" });
}

export function integrationConnectUrl(provider: "microsoft" | "notion"): string {
  return `/api/integrations/${provider}/connect`;
}

export type ContentRevision = {
  id: string;
  entity_type: "article" | "certificate";
  entity_id: string;
  version_number: number;
  changed_by_id: string;
  changed_by_name: string;
  created_at: string;
  snapshot?: Record<string, unknown>;
};

export type VersionChange = {
  field: string;
  from: unknown;
  to: unknown;
};

export type VersionCompareResult = {
  entity_type: string;
  entity_id: string;
  from_version: number;
  to_version: string | number;
  changes: VersionChange[];
};

export async function fetchContentVersions(
  entityType: "article" | "certificate",
  entityId: string,
): Promise<ContentRevision[]> {
  const payload = await request<{ versions: ContentRevision[] }>(
    `/api/versions/${entityType}/${encodeURIComponent(entityId)}`,
  );
  return payload.versions;
}

export async function fetchVersionDetail(versionId: string): Promise<ContentRevision> {
  const payload = await request<{ version: ContentRevision }>(
    `/api/versions/revision/${encodeURIComponent(versionId)}`,
  );
  return payload.version;
}

export async function compareVersions(
  entityType: "article" | "certificate",
  entityId: string,
  fromVersion: number,
  toVersion?: number,
): Promise<VersionCompareResult> {
  const params = new URLSearchParams({ from_version: String(fromVersion) });
  if (toVersion !== undefined) {
    params.set("to_version", String(toVersion));
  }
  return request<VersionCompareResult>(
    `/api/versions/${entityType}/${encodeURIComponent(entityId)}/compare?${params.toString()}`,
  );
}

export async function restoreContentVersion(
  entityType: "article" | "certificate",
  entityId: string,
  versionNumber: number,
): Promise<{ ok: boolean; restored_version: number }> {
  return request<{ ok: boolean; restored_version: number }>(
    `/api/versions/${entityType}/${encodeURIComponent(entityId)}/restore/${versionNumber}`,
    { method: "POST" },
  );
}

export async function fetchWorkflowPending(): Promise<WorkflowPending> {
  return request<WorkflowPending>("/api/workflow/pending");
}

export async function submitArticleForReview(articleId: string): Promise<Article> {
  const payload = await request<{ article: Article }>(`/api/workflow/articles/${articleId}/submit`, {
    method: "POST",
  });
  return payload.article;
}

export async function approveArticle(
  articleId: string,
  scheduledPublishAt?: string | null,
): Promise<Article> {
  const payload = await request<{ article: Article }>(`/api/workflow/articles/${articleId}/approve`, {
    method: "POST",
    body: JSON.stringify({ scheduled_publish_at: scheduledPublishAt || null }),
  });
  return payload.article;
}

export async function rejectArticle(articleId: string, comment: string): Promise<Article> {
  const payload = await request<{ article: Article }>(`/api/workflow/articles/${articleId}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
  return payload.article;
}

export async function requestCertificateRenewal(certificateId: string): Promise<void> {
  await request(`/api/workflow/certificates/${certificateId}/request-renewal`, { method: "POST" });
}

export async function approveCertificateRenewal(certificateId: string): Promise<void> {
  await request(`/api/workflow/certificates/${certificateId}/approve-renewal`, { method: "POST" });
}

export async function rejectCertificateRenewal(certificateId: string, comment: string): Promise<void> {
  await request(`/api/workflow/certificates/${certificateId}/reject-renewal`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export async function fetchAuditLog(limit = 100): Promise<AuditEntry[]> {
  const payload = await request<{ entries: AuditEntry[] }>(`/api/audit?limit=${limit}`);
  return payload.entries;
}
