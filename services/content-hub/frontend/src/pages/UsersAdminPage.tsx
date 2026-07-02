import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createDepartment,
  createInvite,
  createUser,
  deleteDepartment,
  fetchDepartments,
  fetchInvites,
  fetchUsers,
  resendInvite,
  revokeInvite,
  updateDepartment,
  updateUserActive,
  updateUserDepartment,
  updateUserPassword,
  updateUserRole,
  type Department,
  type User,
  type UserInvite,
} from "../api/client";

const ROLES: User["role"][] = ["it_master", "editor", "viewer"];

function slugifyDepartmentCode(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export function UsersAdminPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"employees" | "invites" | "departments">("employees");
  const [users, setUsers] = useState<User[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [newDepartmentName, setNewDepartmentName] = useState("");
  const [newDepartmentCode, setNewDepartmentCode] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState<User["role"]>("editor");
  const [newUserDepartmentId, setNewUserDepartmentId] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<User["role"]>("editor");
  const [inviteDepartmentId, setInviteDepartmentId] = useState("");
  const [lastInviteLink, setLastInviteLink] = useState("");
  const [inviteNotice, setInviteNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [nextUsers, nextDepartments, nextInvites] = await Promise.all([
        fetchUsers(),
        fetchDepartments(true),
        fetchInvites(),
      ]);
      setUsers(nextUsers);
      setDepartments(nextDepartments);
      setInvites(nextInvites);
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
    if (role === user.role) {
      return;
    }
    setBusyId(user.db_id);
    try {
      await updateUserRole(user.db_id, role);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleActiveChange(user: User, isActive: boolean) {
    setBusyId(user.db_id);
    try {
      await updateUserActive(user.db_id, isActive);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDepartmentChange(user: User, departmentId: string) {
    const nextDepartmentId = departmentId || null;
    if (nextDepartmentId === (user.department_id ?? null)) {
      return;
    }
    setBusyId(user.db_id);
    try {
      await updateUserDepartment(user.db_id, nextDepartmentId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleCreateUser(event: React.FormEvent) {
    event.preventDefault();
    if (!newUserName.trim() || !newUserEmail.trim() || newUserPassword.length < 8) {
      return;
    }
    setBusyId("new-user");
    try {
      await createUser({
        name: newUserName.trim(),
        email: newUserEmail.trim(),
        password: newUserPassword,
        role: newUserRole,
        department_id: newUserDepartmentId || null,
      });
      setNewUserName("");
      setNewUserEmail("");
      setNewUserPassword("");
      setNewUserRole("editor");
      setNewUserDepartmentId("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handlePasswordReset(user: User) {
    const nextPassword = window.prompt(t("users.passwordPrompt", { name: user.name }));
    if (!nextPassword || nextPassword.length < 8) {
      return;
    }
    setBusyId(user.db_id);
    try {
      await updateUserPassword(user.db_id, nextPassword);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleCreateDepartment(event: React.FormEvent) {
    event.preventDefault();
    const name = newDepartmentName.trim();
    const code = (newDepartmentCode || slugifyDepartmentCode(name)).trim();
    if (!name || !code) {
      return;
    }
    setBusyId("new-department");
    try {
      await createDepartment({ name, code });
      setNewDepartmentName("");
      setNewDepartmentCode("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDepartmentActiveChange(department: Department, isActive: boolean) {
    setBusyId(department.id);
    try {
      await updateDepartment(department.id, { is_active: isActive });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDeleteDepartment(department: Department) {
    if (!window.confirm(t("departments.confirmDelete", { name: department.name }))) {
      return;
    }
    setBusyId(department.id);
    try {
      await deleteDepartment(department.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleSendInvite(event: React.FormEvent) {
    event.preventDefault();
    if (!inviteEmail.trim()) {
      return;
    }
    setBusyId("new-invite");
    setInviteNotice("");
    setLastInviteLink("");
    try {
      const invite = await createInvite({
        email: inviteEmail.trim(),
        role: inviteRole,
        department_id: inviteDepartmentId || null,
      });
      setInviteEmail("");
      setInviteRole("editor");
      setInviteDepartmentId("");
      setLastInviteLink(invite.invite_url);
      setInviteNotice(
        invite.email_sent ? t("users.invites.sent") : t("users.invites.linkOnly"),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleResendInvite(invite: UserInvite) {
    setBusyId(invite.id);
    setInviteNotice("");
    try {
      const updated = await resendInvite(invite.id);
      setLastInviteLink(updated.invite_url);
      setInviteNotice(
        updated.email_sent ? t("users.invites.resent") : t("users.invites.linkOnly"),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleRevokeInvite(invite: UserInvite) {
    if (!window.confirm(t("users.invites.confirmRevoke", { email: invite.email }))) {
      return;
    }
    setBusyId(invite.id);
    try {
      await revokeInvite(invite.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function copyInviteLink(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setInviteNotice(t("users.invites.copied"));
    } catch {
      setInviteNotice(link);
    }
  }

  const activeDepartments = departments.filter((department) => department.is_active);
  const pendingInvites = invites.filter((invite) => invite.status === "pending");

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("users.title")}</h1>
        <p className="muted">{t("users.subtitle")}</p>
      </header>

      <div className="admin-tabs">
        <button
          type="button"
          className={tab === "employees" ? "admin-tab active" : "admin-tab"}
          onClick={() => setTab("employees")}
        >
          {t("users.tabs.employees")}
        </button>
        <button
          type="button"
          className={tab === "invites" ? "admin-tab active" : "admin-tab"}
          onClick={() => setTab("invites")}
        >
          {t("users.tabs.invites")}
        </button>
        <button
          type="button"
          className={tab === "departments" ? "admin-tab active" : "admin-tab"}
          onClick={() => setTab("departments")}
        >
          {t("users.tabs.departments")}
        </button>
      </div>

      {tab === "employees" ? (
        <div className="role-legend">
          {ROLES.map((role) => (
            <div key={role} className="role-legend-item">
              <strong>{t(`users.roles.${role}`)}</strong>
              <span className="muted">{t(`users.roleDescriptions.${role}`)}</span>
            </div>
          ))}
        </div>
      ) : null}

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && tab === "employees" ? (
        <form className="employee-create-form" onSubmit={(event) => void handleCreateUser(event)}>
          <h2>{t("users.create.title")}</h2>
          <div className="employee-create-grid">
            <input
              type="text"
              value={newUserName}
              placeholder={t("users.create.name")}
              onChange={(event) => setNewUserName(event.target.value)}
              required
            />
            <input
              type="email"
              value={newUserEmail}
              placeholder={t("users.create.email")}
              onChange={(event) => setNewUserEmail(event.target.value)}
              required
            />
            <input
              type="password"
              value={newUserPassword}
              placeholder={t("users.create.password")}
              minLength={8}
              onChange={(event) => setNewUserPassword(event.target.value)}
              required
            />
            <select
              className="admin-select"
              value={newUserRole}
              onChange={(event) => setNewUserRole(event.target.value as User["role"])}
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`users.roles.${role}`)}
                </option>
              ))}
            </select>
            <select
              className="admin-select"
              value={newUserDepartmentId}
              onChange={(event) => setNewUserDepartmentId(event.target.value)}
            >
              <option value="">{t("departments.unassigned")}</option>
              {activeDepartments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
            <button type="submit" className="primary-button" disabled={busyId === "new-user"}>
              {t("users.create.submit")}
            </button>
          </div>
        </form>
      ) : null}

      {!loading && tab === "employees" && users.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{t("users.columns.name")}</th>
                <th>{t("users.columns.email")}</th>
                <th>{t("users.columns.department")}</th>
                <th>{t("users.columns.role")}</th>
                <th>{t("users.columns.platformAccess")}</th>
                <th>{t("users.columns.lastLogin")}</th>
                <th>{t("departments.columns.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const locked = user.role === "it_master";
                const isBusy = busyId === user.db_id;

                return (
                  <tr key={user.db_id}>
                    <td>
                      <strong>{user.name}</strong>
                    </td>
                    <td>{user.email}</td>
                    <td>
                      <select
                        className="admin-select"
                        value={user.department_id ?? ""}
                        disabled={isBusy}
                        onChange={(event) => void handleDepartmentChange(user, event.target.value)}
                      >
                        <option value="">{t("departments.unassigned")}</option>
                        {activeDepartments.map((department) => (
                          <option key={department.id} value={department.id}>
                            {department.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        className="admin-select"
                        value={user.role}
                        disabled={locked || isBusy}
                        onChange={(event) =>
                          void handleRoleChange(user, event.target.value as User["role"])
                        }
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {t(`users.roles.${role}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <label className="access-toggle">
                        <input
                          type="checkbox"
                          checked={user.is_active}
                          disabled={locked || isBusy}
                          onChange={(event) => void handleActiveChange(user, event.target.checked)}
                        />
                        <span>
                          {user.is_active ? t("users.platformAccess.on") : t("users.platformAccess.off")}
                        </span>
                      </label>
                    </td>
                    <td className="muted">
                      {user.last_login_at
                        ? new Date(user.last_login_at).toLocaleString()
                        : t("users.neverLoggedIn")}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={isBusy}
                        onClick={() => void handlePasswordReset(user)}
                      >
                        {t("users.setPassword")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {!loading && tab === "employees" && users.length === 0 ? (
        <p className="muted">{t("users.empty")}</p>
      ) : null}

      {!loading && tab === "invites" ? (
        <>
          <form className="employee-create-form" onSubmit={(event) => void handleSendInvite(event)}>
            <h2>{t("users.invites.createTitle")}</h2>
            <p className="muted">{t("users.invites.createHint")}</p>
            <div className="employee-create-grid">
              <input
                type="email"
                value={inviteEmail}
                placeholder={t("users.create.email")}
                onChange={(event) => setInviteEmail(event.target.value)}
                required
              />
              <select
                className="admin-select"
                value={inviteRole}
                onChange={(event) => setInviteRole(event.target.value as User["role"])}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {t(`users.roles.${role}`)}
                  </option>
                ))}
              </select>
              <select
                className="admin-select"
                value={inviteDepartmentId}
                onChange={(event) => setInviteDepartmentId(event.target.value)}
              >
                <option value="">{t("departments.unassigned")}</option>
                {activeDepartments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
              <button type="submit" className="primary-button" disabled={busyId === "new-invite"}>
                {t("users.invites.send")}
              </button>
            </div>
          </form>

          {inviteNotice ? <p className="invite-notice">{inviteNotice}</p> : null}
          {lastInviteLink ? (
            <div className="invite-link-row">
              <code className="invite-link">{lastInviteLink}</code>
              <button
                type="button"
                className="ghost-button"
                onClick={() => void copyInviteLink(lastInviteLink)}
              >
                {t("users.invites.copyLink")}
              </button>
            </div>
          ) : null}

          {pendingInvites.length > 0 ? (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{t("users.columns.email")}</th>
                    <th>{t("users.columns.role")}</th>
                    <th>{t("users.columns.department")}</th>
                    <th>{t("users.invites.expires")}</th>
                    <th>{t("departments.columns.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingInvites.map((invite) => (
                    <tr key={invite.id}>
                      <td>{invite.email}</td>
                      <td>{t(`users.roles.${invite.role}`)}</td>
                      <td>{invite.department_name ?? t("departments.unassigned")}</td>
                      <td className="muted">{new Date(invite.expires_at).toLocaleString()}</td>
                      <td>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={busyId === invite.id}
                          onClick={() => void handleResendInvite(invite)}
                        >
                          {t("users.invites.resend")}
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={busyId === invite.id}
                          onClick={() => void handleRevokeInvite(invite)}
                        >
                          {t("users.invites.revoke")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">{t("users.invites.empty")}</p>
          )}
        </>
      ) : null}

      {!loading && tab === "departments" ? (
        <>
          <form className="department-form" onSubmit={(event) => void handleCreateDepartment(event)}>
            <input
              type="text"
              value={newDepartmentName}
              placeholder={t("departments.form.name")}
              onChange={(event) => {
                setNewDepartmentName(event.target.value);
                if (!newDepartmentCode) {
                  setNewDepartmentCode(slugifyDepartmentCode(event.target.value));
                }
              }}
            />
            <input
              type="text"
              value={newDepartmentCode}
              placeholder={t("departments.form.code")}
              onChange={(event) => setNewDepartmentCode(event.target.value)}
            />
            <button type="submit" className="primary-button" disabled={busyId === "new-department"}>
              {t("departments.form.add")}
            </button>
          </form>

          {departments.length > 0 ? (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{t("departments.columns.name")}</th>
                    <th>{t("departments.columns.code")}</th>
                    <th>{t("departments.columns.members")}</th>
                    <th>{t("departments.columns.status")}</th>
                    <th>{t("departments.columns.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {departments.map((department) => (
                    <tr key={department.id}>
                      <td>
                        <strong>{department.name}</strong>
                      </td>
                      <td>
                        <code>{department.code}</code>
                      </td>
                      <td>{department.member_count ?? 0}</td>
                      <td>
                        <label className="access-toggle">
                          <input
                            type="checkbox"
                            checked={department.is_active}
                            disabled={busyId === department.id}
                            onChange={(event) =>
                              void handleDepartmentActiveChange(department, event.target.checked)
                            }
                          />
                          <span>
                            {department.is_active
                              ? t("departments.status.active")
                              : t("departments.status.inactive")}
                          </span>
                        </label>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={busyId === department.id}
                          onClick={() => void handleDeleteDepartment(department)}
                        >
                          {t("departments.delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">{t("departments.empty")}</p>
          )}
        </>
      ) : null}
    </section>
  );
}
