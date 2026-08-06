import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import { AuthProvider } from "./hooks/useAuth";
import { ShopApp } from "./pages/ShopApp";
import "./i18n";
import "./styles.css";

const DEFAULT_SHOP_HOSTS = ["fuckco2.shop", "www.fuckco2.shop"];

function isShopHost(): boolean {
  const host = window.location.hostname.toLowerCase();
  if (DEFAULT_SHOP_HOSTS.includes(host)) {
    return true;
  }
  // Allow local preview via ?shop=1 or path /shop when developing
  const params = new URLSearchParams(window.location.search);
  if (params.get("shop") === "1") {
    return true;
  }
  return false;
}

function applyHostChrome(shop: boolean) {
  document.documentElement.lang = document.documentElement.lang || "en";
  if (shop) {
    document.title = "FuckCo2 Shop";
    const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (appleTitle) appleTitle.setAttribute("content", "FuckCo2");
    let manifest = document.querySelector('link[rel="manifest"]') as HTMLLinkElement | null;
    if (!manifest) {
      manifest = document.createElement("link");
      manifest.rel = "manifest";
      document.head.appendChild(manifest);
    }
    manifest.href = "/manifest-shop.webmanifest";
  }
}

const shop = isShopHost();
applyHostChrome(shop);

registerSW({
  immediate: true,
});

const Root = shop ? ShopApp : App;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      {shop ? (
        <Root />
      ) : (
        <AuthProvider>
          <Root />
        </AuthProvider>
      )}
    </BrowserRouter>
  </React.StrictMode>,
);
