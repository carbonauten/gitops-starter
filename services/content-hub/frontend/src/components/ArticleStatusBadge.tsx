import { useTranslation } from "react-i18next";

import type { Article } from "../api/client";

const STATUS_CLASS: Record<Article["status"], string> = {
  draft: "workflow-badge workflow-badge-draft",
  review: "workflow-badge workflow-badge-review",
  scheduled: "workflow-badge workflow-badge-scheduled",
  published: "workflow-badge workflow-badge-published",
  rejected: "workflow-badge workflow-badge-rejected",
};

export function ArticleStatusBadge({ status }: { status: Article["status"] }) {
  const { t } = useTranslation();
  const labelKey =
    status === "published"
      ? "articles.statusPublished"
      : status === "review"
        ? "articles.statusReview"
        : status === "rejected"
          ? "articles.statusRejected"
          : status === "scheduled"
            ? "articles.statusScheduled"
            : "articles.statusDraft";

  return <span className={STATUS_CLASS[status]}>{t(labelKey)}</span>;
}
