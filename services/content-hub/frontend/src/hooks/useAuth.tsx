import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import {
  fetchAuthConfig,
  fetchCurrentUser,
  loginUrl,
  loginWithPassword,
  logout,
  updateUserLanguage,
  type User,
} from "../api/client";
import type { AppLanguage } from "../i18n";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  microsoftAuthEnabled: boolean;
  refresh: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signInWithMicrosoft: () => void;
  signOut: () => Promise<void>;
  setLanguage: (language: AppLanguage) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [microsoftAuthEnabled, setMicrosoftAuthEnabled] = useState(false);

  const refresh = useCallback(async () => {
    const current = await fetchCurrentUser();
    setUser(current);
    if (current?.language) {
      await i18n.changeLanguage(current.language);
    }
  }, [i18n]);

  useEffect(() => {
    void (async () => {
      try {
        const authConfig = await fetchAuthConfig();
        setMicrosoftAuthEnabled(authConfig.microsoft_auth);
        await refresh();
      } finally {
        setLoading(false);
      }
    })();
  }, [refresh]);

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      const loggedInUser = await loginWithPassword(email, password);
      setUser(loggedInUser);
      if (loggedInUser.language) {
        await i18n.changeLanguage(loggedInUser.language);
      }
    },
    [i18n],
  );

  const signInWithMicrosoft = useCallback(() => {
    window.location.href = loginUrl(i18n.language);
  }, [i18n.language]);

  const signOut = useCallback(async () => {
    await logout();
    setUser(null);
    window.location.href = "/login";
  }, []);

  const setLanguage = useCallback(
    async (language: AppLanguage) => {
      await i18n.changeLanguage(language);
      if (user) {
        const updated = await updateUserLanguage(language);
        setUser(updated);
      }
    },
    [i18n, user],
  );

  const value = useMemo(
    () => ({
      user,
      loading,
      microsoftAuthEnabled,
      refresh,
      signInWithPassword,
      signInWithMicrosoft,
      signOut,
      setLanguage,
    }),
    [user, loading, microsoftAuthEnabled, refresh, signInWithPassword, signInWithMicrosoft, signOut, setLanguage],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
