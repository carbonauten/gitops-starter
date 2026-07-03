import { useTranslation } from "react-i18next";

import type { Certificate } from "../api/client";

const STATUS_CLASS: Record<Certificate["status"], string> = {
  valid: "workflow-badge workflow-badge-published",
  expiring: "workflow-badge workflow-badge-expiring",
  expired: "workflow-badge workflow-badge-rejected",
  renewal: "workflow-badge workflow-badge-review",
};

export function CertificateStatusBadge({ status }: { status: Certificate["status"] }) {
  const { t } = useTranslation();
  return <span className={STATUS_CLASS[status]}>{t(`certificates.status.${status}`)}</span>;
}
