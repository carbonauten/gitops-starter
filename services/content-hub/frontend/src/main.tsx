import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

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

const Root = isShopHost() ? ShopApp : App;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      {isShopHost() ? (
        <Root />
      ) : (
        <AuthProvider>
          <Root />
        </AuthProvider>
      )}
    </BrowserRouter>
  </React.StrictMode>,
);
