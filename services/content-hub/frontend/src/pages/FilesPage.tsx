import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  browseFiles,
  deleteFile,
  fetchFileSources,
  fetchOfficeSession,
  fileDownloadUrl,
  outlookConnectUrl,
  signFile,
  uploadFiles,
  type DocumentSignResponse,
  type FileBrowseItem,
  type FileBrowseResult,
  type FileSource,
  type OfficeSession,
} from "../api/client";
import { DocumentSignPanel } from "../components/DocumentSignPanel";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { OfficeOnlinePanel } from "../components/OfficeOnlinePanel";
import { usePermissions } from "../hooks/usePermissions";

const PDF_EXT = /\.pdf$/i;

const OFFICE_EXT = /\.(docx?|xlsx?|pptx?|odt|ods|odp)$/i;
const OFFICE_MIME = /officedocument|msword|ms-excel|ms-powerpoint|opendocument/i;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileTitle(file: FileBrowseItem): string {
  return file.original_name || file.name || file.id;
}

function isHttpUrl(url?: string): boolean {
  return Boolean(url && /^https?:\/\//i.test(url));
}

function isOfficeFile(file: FileBrowseItem): boolean {
  const name = fileTitle(file);
  if (OFFICE_EXT.test(name)) return true;
  return OFFICE_MIME.test(file.content_type || "");
}

function isPdfFile(file: FileBrowseItem): boolean {
  const name = fileTitle(file);
  if (PDF_EXT.test(name)) return true;
  return (file.content_type || "").toLowerCase() === "application/pdf";
}

function fileTypeIcon(file: FileBrowseItem): string {
  const name = fileTitle(file).toLowerCase();
  const type = (file.content_type || "").toLowerCase();
  if (name.endsWith(".pdf") || type === "application/pdf") return "📕";
  if (/\.(jpe?g|png|gif|webp|svg|bmp)$/.test(name) || type.startsWith("image/")) return "🖼️";
  if (/\.docx?$/.test(name) || /msword|wordprocessingml/.test(type)) return "📄";
  if (/\.xlsx?$/.test(name) || /ms-excel|spreadsheetml/.test(type)) return "📊";
  if (/\.pptx?$/.test(name) || /ms-powerpoint|presentationml/.test(type)) return "📽️";
  if (/\.(zip|rar|7z|tar|gz)$/.test(name) || /zip|compressed/.test(type)) return "🗜️";
  return "📎";
}

export function FilesPage() {
  const { t } = useTranslation();
  const { isItMaster } = usePermissions();
  const [sources, setSources] = useState<FileSource[]>([]);
  const [source, setSource] = useState<FileSource["id"]>("platform");
  const [browse, setBrowse] = useState<FileBrowseResult | null>(null);
  const [currentItemId, setCurrentItemId] = useState<string>("root");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [inputEl, setInputEl] = useState<HTMLInputElement | null>(null);
  const [officeSession, setOfficeSession] = useState<OfficeSession | null>(null);
  const [officeOpen, setOfficeOpen] = useState(false);
  const [officeLoading, setOfficeLoading] = useState(false);
  const [officeError, setOfficeError] = useState("");
  const [signFileId, setSignFileId] = useState<string | null>(null);
  const [signResult, setSignResult] = useState<DocumentSignResponse | null>(null);
  const [signOpen, setSignOpen] = useState(false);
  const [signLoading, setSignLoading] = useState(false);
  const [signError, setSignError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError("");
      setNotice("");
      try {
        const [nextSources, nextBrowse] = await Promise.all([
          fetchFileSources(),
          browseFiles(source, currentItemId === "root" ? undefined : currentItemId, query || undefined),
        ]);
        if (cancelled) return;
        setSources(nextSources);
        setBrowse(nextBrowse);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("common.error"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source, currentItemId, query, t]);

  async function reload() {
    setLoading(true);
    setError("");
    try {
      const [nextSources, nextBrowse] = await Promise.all([
        fetchFileSources(),
        browseFiles(source, currentItemId === "root" ? undefined : currentItemId, query || undefined),
      ]);
      setSources(nextSources);
      setBrowse(nextBrowse);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(selected: FileList | null) {
    if (!selected || selected.length === 0 || source !== "platform" || !isItMaster) return;
    setUploading(true);
    setError("");
    setNotice("");
    try {
      const folderId = currentItemId !== "root" ? currentItemId : undefined;
      const uploaded = await uploadFiles(
        Array.from(selected),
        browse?.breadcrumbs.at(-1)?.name || "general",
        folderId,
      );
      setNotice(t("files.uploadSuccess", { count: uploaded.length }));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setUploading(false);
      if (inputEl) inputEl.value = "";
    }
  }

  async function handleDelete(file: FileBrowseItem) {
    if (file.source && file.source !== "platform") return;
    if (!window.confirm(t("files.confirmDelete"))) return;
    await deleteFile(file.id);
    await reload();
  }

  async function openOffice(file: FileBrowseItem) {
    setOfficeOpen(true);
    setOfficeLoading(true);
    setOfficeError("");
    setOfficeSession(null);
    try {
      const session = await fetchOfficeSession(source, file.id);
      setOfficeSession(session);
    } catch (err) {
      setOfficeError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setOfficeLoading(false);
    }
  }

  function closeOffice() {
    setOfficeOpen(false);
    setOfficeSession(null);
    setOfficeError("");
    setOfficeLoading(false);
  }

  async function openSign(file: FileBrowseItem) {
    setSignFileId(file.id);
    setSignOpen(true);
    setSignLoading(true);
    setSignError("");
    setSignResult(null);
    try {
      const result = await signFile(file.id);
      setSignResult(result);
    } catch (err) {
      setSignError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSignLoading(false);
    }
  }

  function closeSign() {
    setSignOpen(false);
    setSignFileId(null);
    setSignResult(null);
    setSignError("");
    setSignLoading(false);
  }

  function handleSignCompleted() {
    setNotice(t("files.signCompletedHint"));
    void reload();
  }

  function selectSource(next: FileSource["id"]) {
    setSource(next);
    setCurrentItemId("root");
    setQuery("");
  }

  function openFolder(folderId: string) {
    setCurrentItemId(folderId);
    setQuery("");
  }

  function goUp() {
    if (!browse?.parent_item_id) {
      setCurrentItemId("root");
      return;
    }
    setCurrentItemId(browse.parent_item_id);
  }

  const currentSource = sources.find((entry) => entry.id === source);
  const files = browse?.files ?? [];
  const folders = browse?.folders ?? [];
  const onedriveSource = sources.find((entry) => entry.id === "onedrive");

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("files.title")}</h1>
        <p className="muted">{t("files.subtitle")}</p>
      </header>

      <div className="file-source-tabs" role="tablist" aria-label={t("files.title")}>
        {(["platform", "sharepoint", "onedrive"] as const).map((entry) => (
          <button
            key={entry}
            type="button"
            role="tab"
            aria-selected={source === entry}
            className={source === entry ? "admin-tab active" : "admin-tab"}
            onClick={() => selectSource(entry)}
          >
            {t(`files.sources.${entry}`)}
          </button>
        ))}
      </div>

      {source === "onedrive" && onedriveSource && !onedriveSource.outlook_connected ? (
        <div className="integration-connect-block outlook-connect-card">
          <div className="integration-connect-header">
            <strong>{t("files.onedriveConnectTitle")}</strong>
            <span className="integration-badge">{t("files.notConnected")}</span>
          </div>
          <p className="muted">{t("files.onedriveConnectHint")}</p>
          {onedriveSource.oauth_available ? (
            <a className="primary-button integration-connect-button" href={outlookConnectUrl()}>
              {t("files.onedriveConnect")}
            </a>
          ) : (
            <p className="muted">{t("files.onedriveEnvMissing")}</p>
          )}
        </div>
      ) : null}

      {currentSource?.mock ? <p className="muted">{t("files.mockHint")}</p> : null}
      {source === "sharepoint" && currentSource && !currentSource.configured ? (
        <p className="muted">{t("files.sharepointHint")}</p>
      ) : null}

      {source === "platform" && isItMaster ? (
        <div
          className="upload-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void handleUpload(event.dataTransfer.files);
          }}
        >
          <p>{t("files.dropHint")}</p>
          <button
            type="button"
            className="primary-button"
            disabled={uploading}
            onClick={() => inputEl?.click()}
          >
            {uploading ? t("common.loading") : t("files.upload")}
          </button>
          <input
            ref={setInputEl}
            type="file"
            multiple
            hidden
            onChange={(event) => void handleUpload(event.target.files)}
          />
        </div>
      ) : null}
      {source === "platform" && !isItMaster ? <p className="muted">{t("files.masterOnlyHint")}</p> : null}
      {notice ? <p className="success-text" role="status">{notice}</p> : null}

      <div className="file-browser">
        <aside className="file-browser-sidebar">
          <h2>{t("files.foldersTitle")}</h2>
          {browse?.breadcrumbs?.length ? (
            <div className="file-breadcrumbs">
              {browse.breadcrumbs.map((crumb, index) => (
                <button
                  key={`${crumb.id}-${index}`}
                  type="button"
                  className="ghost-button"
                  onClick={() => openFolder(crumb.id)}
                  disabled={index === browse.breadcrumbs.length - 1}
                >
                  {crumb.name}
                </button>
              ))}
            </div>
          ) : null}
          {browse?.parent_item_id || (source !== "platform" && currentItemId !== "root") ? (
            <button type="button" className="ghost-button" onClick={goUp}>
              {t("files.up")}
            </button>
          ) : null}
          <div className="file-folder-tree">
            {source === "platform" && currentItemId === "root"
              ? (browse?.folder_tree ?? []).map((folder) => (
                  <button
                    key={folder.id}
                    type="button"
                    className="file-folder-node"
                    onClick={() => openFolder(folder.id)}
                  >
                    📁 {folder.name}
                  </button>
                ))
              : folders.map((folder) => (
                  <button
                    key={folder.id}
                    type="button"
                    className="file-folder-node"
                    onClick={() => openFolder(folder.id)}
                  >
                    📁 {folder.name}
                  </button>
                ))}
          </div>
        </aside>

        <div className="file-browser-main">
          <div className="toolbar">
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("files.searchPlaceholder")}
            />
          </div>

          {loading ? <LoadingState /> : null}
          {error ? <p className="error-text">{error}</p> : null}
          {!loading && files.length === 0 && folders.length === 0 ? (
            <EmptyState message={t("files.empty")} icon="▣" />
          ) : null}

          <div className="list-stack">
            {!loading
              ? folders.map((folder) => (
                  <button
                    key={`folder-${folder.id}`}
                    type="button"
                    className="list-card file-folder-card"
                    onClick={() => openFolder(folder.id)}
                  >
                    <div>
                      <h2>📁 {folder.name}</h2>
                      <p className="muted">{t("files.openFolder")}</p>
                    </div>
                  </button>
                ))
              : null}
            {!loading
              ? files.map((file) => (
                  <article key={`${file.source ?? source}-${file.id}`} className="list-card">
                    <div>
                      <h2>
                        <span aria-hidden="true">{fileTypeIcon(file)}</span> {fileTitle(file)}
                      </h2>
                      <p className="muted">
                        {formatSize(file.size_bytes || 0)}
                        {file.uploaded_by_name ? ` · ${file.uploaded_by_name}` : ""}
                      </p>
                    </div>
                    <div className="list-card-actions">
                      {isOfficeFile(file) ? (
                        <button
                          type="button"
                          className="primary-button"
                          onClick={() => void openOffice(file)}
                        >
                          {t("files.openOffice")}
                        </button>
                      ) : null}
                      {source === "platform" && isPdfFile(file) ? (
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => void openSign(file)}
                        >
                          {t("files.sign")}
                        </button>
                      ) : null}
                      {isHttpUrl(file.web_url) ? (
                        <a
                          href={file.web_url}
                          className="ghost-button link-button"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("files.openExternal")}
                        </a>
                      ) : source === "platform" ? (
                        <a href={fileDownloadUrl(file.id)} className="ghost-button link-button">
                          {t("files.download")}
                        </a>
                      ) : browse?.mock && !isOfficeFile(file) ? (
                        <span className="muted">{t("files.previewOnly")}</span>
                      ) : null}
                      {source === "platform" ? (
                        <button
                          type="button"
                          className="ghost-button danger"
                          onClick={() => void handleDelete(file)}
                        >
                          {t("files.delete")}
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))
              : null}
          </div>
        </div>
      </div>

      {officeOpen ? (
        <OfficeOnlinePanel
          session={officeSession}
          loading={officeLoading}
          error={officeError}
          onClose={closeOffice}
        />
      ) : null}

      {signOpen ? (
        <DocumentSignPanel
          fileId={signFileId}
          result={signResult}
          loading={signLoading}
          error={signError}
          onClose={closeSign}
          onCompleted={handleSignCompleted}
        />
      ) : null}
    </section>
  );
}
