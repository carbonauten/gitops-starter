export type User = {
  id: string;
  name: string;
  email: string;
  language: string;
};

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
  type: "article" | "file";
  id: string;
  title: string;
  snippet: string;
  status?: string | null;
  folder?: string | null;
  updated_at: string;
};

export type DashboardStats = {
  drafts: number;
  published: number;
  files: number;
  certificates: number;
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

  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers,
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
