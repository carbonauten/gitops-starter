export type User = {
  id: string;
  db_id: string;
  name: string;
  email: string;
  role: "it_master" | "editor" | "certificate_manager" | "viewer";
  department_id?: string | null;
  department_name?: string | null;
  language: string;
  is_active: boolean;
  last_login_at?: string | null;
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
  created_by_id: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
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
  type: "scheduled_publish" | "publication" | "certificate_reminder" | "certificate_expiry" | string;
  title: string;
  date: string;
  datetime?: string | null;
  resource_type: string;
  resource_id: string;
  status?: string;
};

export type PublishCalendar = {
  range: { start: string; end: string };
  events: CalendarEvent[];
  by_date: Record<string, CalendarEvent[]>;
};

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const payload = await request<{ stats: DashboardStats }>("/api/dashboard/stats");
  return payload.stats;
}

export async function fetchDashboardHome(): Promise<DashboardHome> {
  const payload = await request<{ home: DashboardHome }>("/api/dashboard/home");
  return payload.home;
}

export async function fetchPublishCalendar(daysAhead = 90, daysBack = 14): Promise<PublishCalendar> {
  const params = new URLSearchParams({
    days_ahead: String(daysAhead),
    days_back: String(daysBack),
  });
  const payload = await request<{ calendar: PublishCalendar }>(`/api/dashboard/calendar?${params}`);
  return payload.calendar;
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

export async function deleteFile(id: string): Promise<void> {
  await request<void>(`/api/files/${id}`, { method: "DELETE" });
}

export function fileDownloadUrl(id: string): string {
  return `/api/files/${id}/download`;
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

export function certificatesExportUrl(): string {
  return "/api/certificates/export";
}

export function certificatesAuditExportUrl(): string {
  return "/api/certificates/audit-export";
}

export async function fetchCertificateChains(): Promise<unknown[]> {
  const payload = await request<{ chains: unknown[] }>("/api/certificates/chains");
  return payload.chains;
}

export async function fetchUsers(): Promise<User[]> {
  const payload = await request<{ users: User[] }>("/api/user/users");
  return payload.users;
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
