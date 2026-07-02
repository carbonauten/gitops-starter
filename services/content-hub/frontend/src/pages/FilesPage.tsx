import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { deleteFile, fetchFiles, fileDownloadUrl, uploadFile, type FileAsset } from "../api/client";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FilesPage() {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<FileAsset[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [folder, setFolder] = useState("general");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const payload = await fetchFiles(query || undefined, folder || undefined);
      setFiles(payload.files);
      setFolders(payload.folders);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [query, folder]);

  async function handleUpload(selected: FileList | null) {
    if (!selected || selected.length === 0) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(selected)) {
        await uploadFile(file, folder);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm(t("files.confirmDelete"))) return;
    await deleteFile(id);
    await load();
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("files.title")}</h1>
        <p className="muted">{t("files.subtitle")}</p>
      </header>

      <div
        className="upload-zone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void handleUpload(event.dataTransfer.files);
        }}
      >
        <p>{t("files.dropHint")}</p>
        <button type="button" className="primary-button" disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? t("common.loading") : t("files.upload")}
        </button>
        <input ref={inputRef} type="file" multiple hidden onChange={(event) => void handleUpload(event.target.files)} />
      </div>

      <div className="toolbar">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("files.searchPlaceholder")}
        />
        <select value={folder} onChange={(event) => setFolder(event.target.value)}>
          <option value="general">{t("files.folderGeneral")}</option>
          <option value="compliance">{t("files.folderCompliance")}</option>
          <option value="marketing">{t("files.folderMarketing")}</option>
          {folders
            .filter((item) => !["general", "compliance", "marketing"].includes(item))
            .map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
        </select>
      </div>

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && files.length === 0 ? <div className="empty-state">{t("files.empty")}</div> : null}

      <div className="list-stack">
        {files.map((file) => (
          <article key={file.id} className="list-card">
            <div>
              <h2>{file.original_name}</h2>
              <p className="muted">
                {file.folder} · {formatSize(file.size_bytes)} · {file.uploaded_by_name}
              </p>
            </div>
            <div className="list-card-actions">
              <a href={fileDownloadUrl(file.id)} className="ghost-button link-button">
                {t("files.download")}
              </a>
              <button type="button" className="ghost-button danger" onClick={() => void handleDelete(file.id)}>
                {t("files.delete")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
