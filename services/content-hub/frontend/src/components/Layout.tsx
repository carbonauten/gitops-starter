import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { LanguageSwitch } from "./LanguageSwitch";
import { SearchBar } from "./SearchBar";
import { BrandLogo } from "./BrandLogo";
import { useAuth } from "../hooks/useAuth";
import { usePermissions } from "../hooks/usePermissions";

type NavItem = {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
};

function NavItems({ items, onNavigate }: { items: NavItem[]; onNavigate: () => void }) {
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
        >
          <span className="nav-link-icon" aria-hidden="true">
            {item.icon}
          </span>
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

export function TopBar({ onMenuToggle }: { onMenuToggle: () => void }) {
  const { t } = useTranslation();
  const { user, signOut } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar-start">
        <button
          type="button"
          className="ghost-button mobile-nav-toggle"
          onClick={onMenuToggle}
          aria-label={t("nav.openMenu")}
        >
          ☰
        </button>
        <BrandLogo size="sm" />
      </div>
      <div className="topbar-search">
        <SearchBar />
      </div>
      <div className="topbar-actions">
        <LanguageSwitch />
        {user ? (
          <div className="user-chip">
            <span className="user-chip-text">
              <strong>{user.name}</strong>
              <span className="role-chip"> · {t(`users.roles.${user.role}`)}</span>
              {user.department_name ? (
                <span className="role-chip"> · {user.department_name}</span>
              ) : null}
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

export function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const { t } = useTranslation();
  const { canManageUsers, canManageShop, canApprove, canApproveCertificates } = usePermissions();

  const overview: NavItem[] = [
    { to: "/search", label: t("nav.search"), icon: "⌕" },
    { to: "/", label: t("nav.dashboard"), end: true, icon: "◆" },
  ];

  const content: NavItem[] = [
    { to: "/articles", label: t("nav.articles"), icon: "✎" },
    { to: "/files", label: t("nav.files"), icon: "▣" },
    { to: "/certificates", label: t("nav.certificates"), icon: "◎" },
  ];

  const shop: NavItem[] = canManageShop
    ? [
        { to: "/products", label: t("nav.products"), icon: "◈" },
        { to: "/orders", label: t("nav.orders"), icon: "☰" },
        { to: "/shop-customers", label: t("nav.shopCustomers"), icon: "☺" },
        { to: "/shop-monitoring", label: t("nav.shopMonitoring"), icon: "▥" },
      ]
    : [];

  const publishing: NavItem[] = [
    { to: "/publish", label: t("nav.publish"), end: true, icon: "↗" },
    { to: "/calendar", label: t("nav.calendar"), icon: "▦" },
    { to: "/analytics", label: t("nav.analytics"), icon: "▥" },
  ];

  if (canApprove || canApproveCertificates) {
    publishing.push({ to: "/workflow", label: t("nav.workflow"), icon: "✓" });
  }

  const admin: NavItem[] = canManageUsers
    ? [
        { to: "/users", label: t("nav.users"), icon: "☰" },
        { to: "/audit", label: t("nav.audit"), icon: "≡" },
      ]
    : [];

  return (
    <aside className={`sidebar${open ? " sidebar-open" : ""}`}>
      <nav>
        <div className="nav-section-label">{t("nav.overviewSection")}</div>
        <NavItems items={overview} onNavigate={onNavigate} />

        <div className="nav-section-label">{t("nav.contentSection")}</div>
        <NavItems items={content} onNavigate={onNavigate} />

        {shop.length > 0 ? (
          <>
            <div className="nav-section-label">{t("nav.shopSection")}</div>
            <NavItems items={shop} onNavigate={onNavigate} />
          </>
        ) : null}

        <div className="nav-section-label">{t("nav.publishSection")}</div>
        <NavItems items={publishing} onNavigate={onNavigate} />

        {admin.length > 0 ? (
          <>
            <div className="nav-section-label">{t("nav.adminSection")}</div>
            <NavItems items={admin} onNavigate={onNavigate} />
          </>
        ) : null}
      </nav>
    </aside>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="app-shell">
      <TopBar onMenuToggle={() => setNavOpen((current) => !current)} />
      <div className="app-body">
        {navOpen ? (
          <button
            type="button"
            className="sidebar-backdrop"
            aria-label={t("nav.closeMenu")}
            onClick={() => setNavOpen(false)}
          />
        ) : null}
        <Sidebar open={navOpen} onNavigate={() => setNavOpen(false)} />
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
