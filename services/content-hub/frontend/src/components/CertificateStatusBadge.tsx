import { useTranslation } from "react-i18next";

import type { Certificate } from "../api/client";

const STATUS_CLASS: Record<Certificate["status"], string> = {
  valid: "workflow-badge workflow-badge-published",
  expiring: "workflow-badge workflow-badge-expiring",
  expired: "workflow-badge workflow-badge-rejected",
  renewal: "workflow-badge workflow-badge-review",
};

export function CertificateStatusBadge({ status }: { status: Certificate["status"] | string }) {
  const { t } = useTranslation();
  const className = STATUS_CLASS[status as Certificate["status"]] || "workflow-badge workflow-badge-review";
  return <span className={className}>{t(`certificates.status.${status}`, { defaultValue: status })}</span>;
}
