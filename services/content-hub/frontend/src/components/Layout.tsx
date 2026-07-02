import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { LanguageSwitch } from "./LanguageSwitch";
import { SearchBar } from "./SearchBar";
import { BrandLogo } from "./BrandLogo";
import { useAuth } from "../hooks/useAuth";

export function TopBar() {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();

  return (
    <header className="topbar">
      <BrandLogo />
      <div className="topbar-actions">
        <SearchBar />
        <LanguageSwitch />
        {user ? (
          <div className="user-chip">
            <span>
              {t("auth.signedInAs")} <strong>{user.name}</strong>
            </span>
            <button type="button" className="ghost-button" onClick={() => void signOut()}>
              {t("auth.signOut")}
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}

export function Sidebar() {
  const { t } = useTranslation();

  const items = [
    { to: "/", label: t("nav.dashboard"), end: true },
    { to: "/articles", label: t("nav.articles") },
    { to: "/files", label: t("nav.files") },
    { to: "/certificates", label: t("nav.certificates") },
    { to: "/publish", label: t("nav.publish") },
  ];

  return (
    <aside className="sidebar">
      <nav>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <TopBar />
      <div className="app-body">
        <Sidebar />
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
