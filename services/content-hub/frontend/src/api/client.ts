export type User = {
  id: string;
  db_id: string;
  name: string;
  email: string;
  role: "it_master" | "editor" | "viewer";
  language: string;
  is_active: boolean;
  last_login_at?: string | null;
};

export function canEditContent(role: User["role"]): boolean {
  return role === "it_master" || role === "editor";
}

export function canManageUsers(role: User["role"]): boolean {
  return role === "it_master";
}

export type Article = {
  id: string;
  title: string;
  content: string;
  status: "draft" | "published";
  template: string | null;
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
  uploaded_by_id: string;
  uploaded_by_name: string;
  created_at: string;
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
};

export type Certificate = {
  id: string;
  name: string;
  category: "compliance" | "product" | "training" | "ssl";
  issuer: string;
  valid_from: string;
  valid_to: string;
  renewal_in_progress: boolean;
  status: "valid" | "expiring" | "expired" | "renewal";
  days_until_expiry: number;
  responsible_name: string;
  responsible_email: string;
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
  published: number;
  files: number;
  certificates: number;
  expiring_30: number;
  expiring_60: number;
  expiring_90: number;
};

type ApiError = {
  error: string;
  code: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(path, {
      credentials: "include",
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      let message = "Request failed";
      try {
        const payload = (await response.json()) as ApiError;
        message = payload.error ?? message;
      } catch {
        // ignore parse errors
      }
      throw new Error(message);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
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

export function loginUrl(language: string): string {
  return `/api/auth/login?lang=${encodeURIComponent(language)}`;
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const payload = await request<{ stats: DashboardStats }>("/api/dashboard/stats");
  return payload.stats;
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

export async function fetchFiles(q?: string, folder?: string): Promise<{ files: FileAsset[]; folders: string[] }> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (folder) params.set("folder", folder);
  const query = params.toString();
  return request<{ files: FileAsset[]; folders: string[] }>(`/api/files${query ? `?${query}` : ""}`);
}

export async function uploadFile(file: File, folder: string): Promise<FileAsset> {
  const body = new FormData();
  body.append("upload", file);
  body.append("folder", folder);
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

export async function searchContent(q: string): Promise<SearchResult[]> {
  const payload = await request<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q)}`);
  return payload.results;
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
  data: Omit<Certificate, "id" | "status" | "days_until_expiry" | "file_name" | "created_by_id" | "created_by_name" | "created_at" | "updated_at">,
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

export async function fetchUsers(): Promise<User[]> {
  const payload = await request<{ users: User[] }>("/api/user/users");
  return payload.users;
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
