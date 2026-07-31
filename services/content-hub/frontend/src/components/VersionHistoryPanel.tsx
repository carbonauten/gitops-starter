import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  compareVersions,
  fetchContentVersions,
  fetchVersionDetail,
  restoreContentVersion,
  type ContentRevision,
  type VersionChange,
} from "../api/client";

type VersionHistoryPanelProps = {
  entityType: "article" | "certificate";
  entityId: string;
  onRestored?: () => void;
};

export function VersionHistoryPanel({ entityType, entityId, onRestored }: VersionHistoryPanelProps) {
  const { t } = useTranslation();
  const [versions, setVersions] = useState<ContentRevision[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [changes, setChanges] = useState<VersionChange[]>([]);
  const [compareLabel, setCompareLabel] = useState("");

  async function loadVersions() {
    setLoading(true);
    setError("");
    try {
      setVersions(await fetchContentVersions(entityType, entityId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadVersions();
  }, [entityType, entityId]);

  async function handleCompare(versionNumber: number) {
    setError("");
    try {
      const result = await compareVersions(entityType, entityId, versionNumber);
      setSelectedVersion(versionNumber);
      setChanges(result.changes);
      setCompareLabel(
        t("versions.compareLabel", {
          from: versionNumber,
          to: result.to_version === "current" ? t("versions.current") : result.to_version,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  async function handleView(versionId: string) {
    setError("");
    try {
      const detail = await fetchVersionDetail(versionId);
      const snapshot = detail.snapshot || {};
      setSelectedVersion(detail.version_number);
      setCompareLabel(t("versions.snapshotLabel", { version: detail.version_number }));
      setChanges(
        Object.entries(snapshot).map(([field, value]) => ({
          field,
          from: null,
          to: value,
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  async function handleRestore(versionNumber: number) {
    if (!window.confirm(t("versions.confirmRestore", { number: versionNumber }))) return;
    setRestoring(versionNumber);
    setError("");
    setNotice("");
    try {
      await restoreContentVersion(entityType, entityId, versionNumber);
      setNotice(t("versions.restored", { number: versionNumber }));
      setSelectedVersion(null);
      setChanges([]);
      await loadVersions();
      onRestored?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setRestoring(null);
    }
  }

  function formatValue(value: unknown): string {
    if (value === null || value === undefined) {
      return "—";
    }
    if (typeof value === "boolean") {
      return value ? t("common.yes") : t("common.no");
    }
    const text = String(value);
    return text.length > 180 ? `${text.slice(0, 180)}…` : text;
  }

  return (
    <section className="version-history-panel">
      <h2>{t("versions.title")}</h2>
      <p className="muted">{t("versions.subtitle")}</p>
      {loading ? <p>{t("common.loading")}</p> : null}
      {notice ? <p className="success-text" role="status">{notice}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && versions.length === 0 ? <p className="muted">{t("versions.empty")}</p> : null}
      {versions.length > 0 ? (
        <div className="version-history-layout">
          <ul className="version-history-list">
            {versions.map((version) => (
              <li key={version.id} className="version-history-item">
                <div>
                  <strong>
                    {t("versions.versionNumber", { number: version.version_number })}
                  </strong>
                  <div className="muted">
                    {version.changed_by_name} · {new Date(version.created_at).toLocaleString()}
                  </div>
                </div>
                <div className="version-history-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleView(version.id)}
                  >
                    {t("versions.view")}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleCompare(version.version_number)}
                  >
                    {t("versions.compareCurrent")}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={restoring === version.version_number}
                    onClick={() => void handleRestore(version.version_number)}
                  >
                    {restoring === version.version_number
                      ? t("common.loading")
                      : t("versions.restore")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {selectedVersion !== null ? (
            <div className="version-diff-panel">
              <h3>{compareLabel}</h3>
              {changes.length === 0 ? (
                <p className="muted">{t("versions.noChanges")}</p>
              ) : (
                <div className="version-diff-list">
                  {changes.map((change) => (
                    <div key={change.field} className="version-diff-item">
                      <strong>{t(`versions.fields.${change.field}`, { defaultValue: change.field })}</strong>
                      {change.from !== null ? (
                        <div className="version-diff-from">
                          <span className="muted">{t("versions.before")}</span>
                          <pre>{formatValue(change.from)}</pre>
                        </div>
                      ) : null}
                      <div className="version-diff-to">
                        <span className="muted">
                          {change.from !== null ? t("versions.after") : t("versions.value")}
                        </span>
                        <pre>{formatValue(change.to)}</pre>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
