import { useTranslation } from "react-i18next";

import type { PublicationDelivery } from "../api/client";

const STATUS_CLASS: Record<PublicationDelivery["status"], string> = {
  pending: "workflow-badge workflow-badge-scheduled",
  sent: "workflow-badge workflow-badge-published",
  failed: "workflow-badge workflow-badge-rejected",
};

export function DeliveryStatusBadge({ status }: { status: PublicationDelivery["status"] }) {
  const { t } = useTranslation();
  return <span className={STATUS_CLASS[status]}>{t(`publish.status.${status}`)}</span>;
}
