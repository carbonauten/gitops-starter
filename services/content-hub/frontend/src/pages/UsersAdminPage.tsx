import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchUsers, updateUserActive, updateUserRole, type User } from "../api/client";

const ROLES: User["role"][] = ["it_master", "editor", "viewer"];

export function UsersAdminPage() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setUsers(await fetchUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleRoleChange(user: User, role: User["role"]) {
    await updateUserRole(user.db_id, role);
    await load();
  }

  async function handleActiveChange(user: User, isActive: boolean) {
    await updateUserActive(user.db_id, isActive);
    await load();
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("users.title")}</h1>
        <p className="muted">{t("users.subtitle")}</p>
      </header>

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <div className="list-stack">
        {users.map((user) => (
          <article key={user.db_id} className="list-card">
            <div>
              <h2>{user.name}</h2>
              <p className="muted">{user.email}</p>
              <p className="muted">
                {t(`users.roles.${user.role}`)}
                {user.last_login_at ? ` · ${t("users.lastLogin")}: ${new Date(user.last_login_at).toLocaleString()}` : ""}
              </p>
            </div>
            <div className="list-card-actions">
              <select
                value={user.role}
                onChange={(event) => void handleRoleChange(user, event.target.value as User["role"])}
                disabled={user.role === "it_master"}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {t(`users.roles.${role}`)}
                  </option>
                ))}
              </select>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={user.is_active}
                  onChange={(event) => void handleActiveChange(user, event.target.checked)}
                  disabled={user.role === "it_master"}
                />
                {t("users.active")}
              </label>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
