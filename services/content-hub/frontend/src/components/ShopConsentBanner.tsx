import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export type ShopConsentChoices = {
  necessary: true;
  preferences: boolean;
  analytics: boolean;
  marketing: boolean;
  decidedAt: string;
};

const STORAGE_KEY = "fuckco2-shop-consent-v1";

export function loadShopConsent(): ShopConsentChoices | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ShopConsentChoices;
    if (!parsed?.decidedAt) return null;
    return {
      necessary: true,
      preferences: Boolean(parsed.preferences),
      analytics: Boolean(parsed.analytics),
      marketing: Boolean(parsed.marketing),
      decidedAt: parsed.decidedAt,
    };
  } catch {
    return null;
  }
}

export function saveShopConsent(choices: Omit<ShopConsentChoices, "necessary" | "decidedAt">): ShopConsentChoices {
  const payload: ShopConsentChoices = {
    necessary: true,
    preferences: Boolean(choices.preferences),
    analytics: Boolean(choices.analytics),
    marketing: Boolean(choices.marketing),
    decidedAt: new Date().toISOString(),
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent("shop-consent-updated", { detail: payload }));
  return payload;
}

export function clearShopConsentDecision() {
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent("shop-consent-updated", { detail: null }));
}

export function ShopConsentBanner({ privacyHref }: { privacyHref: string }) {
  const { t } = useTranslation();
  const [consent, setConsent] = useState<ShopConsentChoices | null>(null);
  const [ready, setReady] = useState(false);
  const [customize, setCustomize] = useState(false);
  const [preferences, setPreferences] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);

  useEffect(() => {
    const current = loadShopConsent();
    setConsent(current);
    if (current) {
      setPreferences(current.preferences);
      setAnalytics(current.analytics);
      setMarketing(current.marketing);
    }
    setReady(true);

    function onUpdate(event: Event) {
      const detail = (event as CustomEvent<ShopConsentChoices | null>).detail;
      setConsent(detail);
    }
    window.addEventListener("shop-consent-updated", onUpdate);
    return () => window.removeEventListener("shop-consent-updated", onUpdate);
  }, []);

  if (!ready || consent) {
    return null;
  }

  function acceptAll() {
    setConsent(saveShopConsent({ preferences: true, analytics: true, marketing: true }));
  }

  function acceptEssential() {
    setConsent(saveShopConsent({ preferences: false, analytics: false, marketing: false }));
  }

  function saveCustom() {
    setConsent(saveShopConsent({ preferences, analytics, marketing }));
    setCustomize(false);
  }

  return (
    <div className="shop-cmp" role="dialog" aria-labelledby="shop-cmp-title" aria-modal="false">
      <div className="shop-cmp-panel">
        <div className="shop-cmp-copy">
          <h2 id="shop-cmp-title">{t("shop.cmp.title")}</h2>
          <p>{t("shop.cmp.body")}</p>
          <p className="muted">
            <Link to={privacyHref}>{t("shop.privacy")}</Link>
          </p>
        </div>

        {customize ? (
          <div className="shop-cmp-options">
            <label className="checkbox-row">
              <input type="checkbox" checked disabled />
              <span>
                <strong>{t("shop.cmp.necessary")}</strong>
                <span className="muted"> — {t("shop.cmp.necessaryHint")}</span>
              </span>
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={preferences} onChange={(e) => setPreferences(e.target.checked)} />
              <span>
                <strong>{t("shop.cmp.preferences")}</strong>
                <span className="muted"> — {t("shop.cmp.preferencesHint")}</span>
              </span>
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={analytics} onChange={(e) => setAnalytics(e.target.checked)} />
              <span>
                <strong>{t("shop.cmp.analytics")}</strong>
                <span className="muted"> — {t("shop.cmp.analyticsHint")}</span>
              </span>
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
              <span>
                <strong>{t("shop.cmp.marketing")}</strong>
                <span className="muted"> — {t("shop.cmp.marketingHint")}</span>
              </span>
            </label>
            <div className="shop-cmp-actions">
              <button type="button" className="primary-button" onClick={saveCustom}>
                {t("shop.cmp.save")}
              </button>
              <button type="button" className="ghost-button" onClick={() => setCustomize(false)}>
                {t("common.close")}
              </button>
            </div>
          </div>
        ) : (
          <div className="shop-cmp-actions">
            <button type="button" className="primary-button" onClick={acceptAll}>
              {t("shop.cmp.acceptAll")}
            </button>
            <button type="button" className="ghost-button" onClick={acceptEssential}>
              {t("shop.cmp.essentialOnly")}
            </button>
            <button type="button" className="ghost-button" onClick={() => setCustomize(true)}>
              {t("shop.cmp.customize")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
