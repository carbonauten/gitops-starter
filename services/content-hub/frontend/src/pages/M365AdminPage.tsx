import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  askM365Directory,
  createM365User,
  fetchM365Status,
  fetchM365Users,
  resetM365Password,
  setM365UserEnabled,
  type M365DirectoryUser,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

export function M365AdminPage() {
  const { t, i18n } = useTranslation();
  const [users, setUsers] = useState<M365DirectoryUser[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mock, setMock] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [newName, setNewName] = useState("");
  const [newUpn, setNewUpn] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDepartment, setNewDepartment] = useState("");
  const [askInput, setAskInput] = useState("");
  const [askAnswer, setAskAnswer] = useState("");
  const [askLoading, setAskLoading] = useState(false);

  async function load(nextQuery = query) {
    setLoading(true);
    setError("");
    try {
      const [listing, status] = await Promise.all([fetchM365Users(nextQuery), fetchM365Status()]);
      setUsers(listing.users);
      setMock(listing.mock || status.mock);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load("");
  }, []);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    await load(query);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!newName.trim() || !newUpn.trim()) {
      return;
    }
    setBusyId("create");
    setError("");
    setNotice("");
    try {
      const created = await createM365User({
        display_name: newName.trim(),
        user_principal_name: newUpn.trim(),
        job_title: newTitle.trim(),
        department: newDepartment.trim(),
      });
      setNewName("");
      setNewUpn("");
      setNewTitle("");
      setNewDepartment("");
      setNotice(
        t("m365.createdNotice", {
          name: created.user.display_name,
          password: created.temporary_password,
        }),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleEnabled(user: M365DirectoryUser, enabled: boolean) {
    setBusyId(user.id);
    setError("");
    try {
      await setM365UserEnabled(user.id, enabled);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleReset(user: M365DirectoryUser) {
    if (!window.confirm(t("m365.confirmReset", { name: user.display_name }))) {
      return;
    }
    setBusyId(user.id);
    setError("");
    try {
      const result = await resetM365Password(user.id);
      setNotice(t("m365.resetNotice", { name: result.user.display_name, password: result.temporary_password }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const question = askInput.trim();
    if (question.length < 2) {
      return;
    }
    setAskLoading(true);
    setError("");
    try {
      const result = await askM365Directory(question, i18n.language);
      setAskAnswer(result.answer);
      if (result.action !== "list") {
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setAskLoading(false);
    }
  }

  const enabledCount = users.filter((item) => item.account_enabled).length;

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">{t("m365.eyebrow")}</p>
        <h1>{t("m365.title")}</h1>
        <p className="muted">{t("m365.subtitle")}</p>
      </header>

      {mock ? <p className="muted">{t("m365.mockHint")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}

      <div className="role-legend">
        <div className="role-legend-item">
          <strong>{users.length}</strong>
          <span className="muted">{t("m365.statUsers")}</span>
        </div>
        <div className="role-legend-item">
          <strong>{enabledCount}</strong>
          <span className="muted">{t("m365.statEnabled")}</span>
        </div>
        <div className="role-legend-item">
          <strong>{users.length - enabledCount}</strong>
          <span className="muted">{t("m365.statBlocked")}</span>
        </div>
      </div>

      <form className="employee-create-form" onSubmit={(event) => void handleAsk(event)}>
        <h2>{t("m365.askTitle")}</h2>
        <p className="muted">{t("m365.askHint")}</p>
        <div className="employee-create-grid">
          <input
            type="text"
            value={askInput}
            placeholder={t("m365.askPlaceholder")}
            onChange={(event) => setAskInput(event.target.value)}
            style={{ gridColumn: "1 / -2" }}
          />
          <button type="submit" className="primary-button" disabled={askLoading}>
            {askLoading ? t("common.loading") : t("m365.askSubmit")}
          </button>
        </div>
        {askAnswer ? <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>{askAnswer}</pre> : null}
      </form>

      <form className="employee-create-form" onSubmit={(event) => void handleCreate(event)}>
        <h2>{t("m365.createTitle")}</h2>
        <div className="employee-create-grid">
          <input
            type="text"
            value={newName}
            placeholder={t("m365.createName")}
            onChange={(event) => setNewName(event.target.value)}
            required
          />
          <input
            type="email"
            value={newUpn}
            placeholder={t("m365.createUpn")}
            onChange={(event) => setNewUpn(event.target.value)}
            required
          />
          <input
            type="text"
            value={newTitle}
            placeholder={t("m365.createTitleField")}
            onChange={(event) => setNewTitle(event.target.value)}
          />
          <input
            type="text"
            value={newDepartment}
            placeholder={t("m365.createDepartment")}
            onChange={(event) => setNewDepartment(event.target.value)}
          />
          <button type="submit" className="primary-button" disabled={busyId === "create"}>
            {t("m365.createSubmit")}
          </button>
        </div>
      </form>

      <form className="toolbar" onSubmit={(event) => void handleSearch(event)}>
        <input
          type="search"
          value={query}
          placeholder={t("m365.searchPlaceholder")}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="ghost-button">
          {t("m365.search")}
        </button>
      </form>

      {loading ? <LoadingState /> : null}
      {!loading && users.length === 0 ? <EmptyState title={t("m365.empty")} /> : null}

      {!loading && users.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{t("m365.columns.name")}</th>
                <th>{t("m365.columns.upn")}</th>
                <th>{t("m365.columns.job")}</th>
                <th>{t("m365.columns.department")}</th>
                <th>{t("m365.columns.licenses")}</th>
                <th>{t("m365.columns.status")}</th>
                <th>{t("m365.columns.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const busy = busyId === user.id;
                return (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.display_name}</strong>
                      <div className="muted">{user.user_type}</div>
                    </td>
                    <td>{user.user_principal_name}</td>
                    <td>{user.job_title || "—"}</td>
                    <td>{user.department || "—"}</td>
                    <td>{user.licenses.length ? user.licenses.join(", ") : t("m365.noLicense")}</td>
                    <td>
                      <span
                        className={
                          user.account_enabled
                            ? "workflow-badge workflow-badge-published"
                            : "workflow-badge workflow-badge-rejected"
                        }
                      >
                        {user.account_enabled ? t("m365.enabled") : t("m365.disabled")}
                      </span>
                    </td>
                    <td>
                      <div className="list-card-actions">
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={busy}
                          onClick={() => void handleEnabled(user, !user.account_enabled)}
                        >
                          {user.account_enabled ? t("m365.block") : t("m365.unblock")}
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={busy}
                          onClick={() => void handleReset(user)}
                        >
                          {t("m365.resetPassword")}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
