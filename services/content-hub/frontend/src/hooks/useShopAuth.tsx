import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  fetchShopCustomerMe,
  loginShopCustomer,
  logoutShopCustomer,
  registerShopCustomer,
  type ShopCustomer,
} from "../api/client";

type ShopAuthContextValue = {
  customer: ShopCustomer | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; name: string; password: string; language?: string }) => Promise<void>;
  logout: () => Promise<void>;
};

const ShopAuthContext = createContext<ShopAuthContextValue | null>(null);

export function ShopAuthProvider({ children }: { children: React.ReactNode }) {
  const [customer, setCustomer] = useState<ShopCustomer | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const next = await fetchShopCustomerMe();
    setCustomer(next);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        await refresh();
      } finally {
        setLoading(false);
      }
    })();
  }, [refresh]);

  const value = useMemo<ShopAuthContextValue>(
    () => ({
      customer,
      loading,
      refresh,
      async login(email, password) {
        const next = await loginShopCustomer({ email, password });
        setCustomer(next);
      },
      async register(data) {
        const next = await registerShopCustomer(data);
        setCustomer(next);
      },
      async logout() {
        await logoutShopCustomer();
        setCustomer(null);
      },
    }),
    [customer, loading, refresh],
  );

  return <ShopAuthContext.Provider value={value}>{children}</ShopAuthContext.Provider>;
}

export function useShopAuth() {
  const ctx = useContext(ShopAuthContext);
  if (!ctx) {
    throw new Error("useShopAuth must be used within ShopAuthProvider");
  }
  return ctx;
}
