import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { ShopProduct } from "../api/client";

export type CartLine = {
  product_id: string;
  slug: string;
  name: string;
  price_cents: number;
  currency: string;
  image_url?: string | null;
  quantity: number;
};

type CartContextValue = {
  items: CartLine[];
  count: number;
  subtotalCents: number;
  addItem: (product: ShopProduct, quantity?: number) => void;
  setQuantity: (productId: string, quantity: number) => void;
  removeItem: (productId: string) => void;
  clear: () => void;
};

const STORAGE_KEY = "fuckco2-shop-cart-v1";
const CartContext = createContext<CartContextValue | null>(null);

function loadCart(): CartLine[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CartLine[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function ShopCartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartLine[]>([]);

  useEffect(() => {
    setItems(loadCart());
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const value = useMemo<CartContextValue>(() => {
    return {
      items,
      count: items.reduce((sum, item) => sum + item.quantity, 0),
      subtotalCents: items.reduce((sum, item) => sum + item.price_cents * item.quantity, 0),
      addItem(product, quantity = 1) {
        setItems((current) => {
          const existing = current.find((item) => item.product_id === product.id);
          if (existing) {
            return current.map((item) =>
              item.product_id === product.id
                ? { ...item, quantity: Math.min(999, item.quantity + quantity) }
                : item,
            );
          }
          return [
            ...current,
            {
              product_id: product.id,
              slug: product.slug,
              name: product.name,
              price_cents: product.price_cents,
              currency: product.currency,
              image_url: product.image_url,
              quantity,
            },
          ];
        });
      },
      setQuantity(productId, quantity) {
        setItems((current) =>
          current
            .map((item) => (item.product_id === productId ? { ...item, quantity } : item))
            .filter((item) => item.quantity > 0),
        );
      },
      removeItem(productId) {
        setItems((current) => current.filter((item) => item.product_id !== productId));
      },
      clear() {
        setItems([]);
      },
    };
  }, [items]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useShopCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useShopCart must be used within ShopCartProvider");
  }
  return context;
}
