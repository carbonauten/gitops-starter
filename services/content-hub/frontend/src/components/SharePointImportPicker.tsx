import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { browseFiles, type FileBrowseItem, type FileBrowseResult } from "../api/client";
import { LoadingState } from "./LoadingState";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  onSelect: (file: FileBrowseItem) => Promise<void> | void;
  selecting?: boolean;
};

export function SharePointImportPicker({ open, title, onClose, onSelect, selecting = false }: Props) {
  const { t } = useTranslation();
  const [browse, setBrowse] = useState<FileBrowseResult | null>(null);
  const [itemId, setItemId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await browseFiles("sharepoint", itemId);
        if (!cancelled) {
          setBrowse(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("common.error"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, itemId, t]);

  useEffect(() => {
    if (!open) {
      setItemId(undefined);
      setBrowse(null);
      setError("");
    }
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="office-panel-backdrop" role="presentation" onClick={onClose}>
      <div
        className="office-panel sharepoint-import-panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="office-panel-header">
          <div>
            <p className="eyebrow">{t("certificates.sharepointImportEyebrow")}</p>
            <h2>{title}</h2>
            <p className="muted">{t("certificates.sharepointImportHint")}</p>
          </div>
          <div className="office-panel-actions">
            <button type="button" className="ghost-button" onClick={onClose} disabled={selecting}>
              {t("common.cancel")}
            </button>
          </div>
        </div>

        {browse?.breadcrumbs?.length ? (
          <nav className="sharepoint-import-breadcrumbs" aria-label={t("certificates.sharepointBreadcrumbs")}>
            {browse.breadcrumbs.map((crumb, index) => (
              <button
                key={crumb.id}
                type="button"
                className="ghost-button"
                disabled={selecting || index === browse.breadcrumbs.length - 1}
                onClick={() => setItemId(crumb.id === "root" ? undefined : crumb.id)}
              >
                {crumb.name}
              </button>
            ))}
          </nav>
        ) : null}

        {browse?.mock ? <p className="muted">{t("certificates.sharepointMockHint")}</p> : null}
        {loading ? <LoadingState /> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {!loading && browse ? (
          <div className="sharepoint-import-lists">
            <div>
              <h3>{t("certificates.sharepointFolders")}</h3>
              {browse.folders.length === 0 ? (
                <p className="muted">{t("certificates.sharepointNoFolders")}</p>
              ) : (
                <ul className="sharepoint-import-list">
                  {browse.folders.map((folder) => (
                    <li key={folder.id}>
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={selecting}
                        onClick={() => setItemId(folder.id)}
                      >
                        📁 {folder.name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3>{t("certificates.sharepointFiles")}</h3>
              {browse.files.length === 0 ? (
                <p className="muted">{t("certificates.sharepointNoFiles")}</p>
              ) : (
                <ul className="sharepoint-import-list">
                  {browse.files.map((file) => (
                    <li key={file.id}>
                      <button
                        type="button"
                        className="primary-button"
                        disabled={selecting}
                        onClick={() => void onSelect(file)}
                      >
                        {selecting ? t("certificates.sharepointImporting") : file.name || file.original_name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
