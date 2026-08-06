import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISS_KEY = "pwa-install-dismissed";

export function PwaInstallBanner({ variant = "platform" }: { variant?: "platform" | "shop" }) {
  const { t } = useTranslation();
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(display-mode: standalone)").matches) return;
    if (localStorage.getItem(DISMISS_KEY) === "1") return;

    const onPrompt = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (!visible || !deferred) return null;

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    setVisible(false);
    setDeferred(null);
  }

  function dismiss() {
    localStorage.setItem(DISMISS_KEY, "1");
    setVisible(false);
  }

  return (
    <div className={`pwa-install-banner ${variant === "shop" ? "pwa-install-banner-shop" : ""}`} role="status">
      <div>
        <strong>{t("pwa.installTitle")}</strong>
        <p className="muted">{t("pwa.installHint")}</p>
      </div>
      <div className="pwa-install-actions">
        <button type="button" className="primary-button" onClick={() => void install()}>
          {t("pwa.install")}
        </button>
        <button type="button" className="ghost-button" onClick={dismiss}>
          {t("pwa.dismiss")}
        </button>
      </div>
    </div>
  );
}
