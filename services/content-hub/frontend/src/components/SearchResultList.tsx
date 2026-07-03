import { useTranslation } from "react-i18next";

import type { Article, Certificate, SearchResult } from "../api/client";
import { ArticleStatusBadge } from "./ArticleStatusBadge";
import { CertificateStatusBadge } from "./CertificateStatusBadge";

function typeLabel(type: SearchResult["type"], t: (key: string) => string): string {
  if (type === "article") return t("nav.articles");
  if (type === "certificate") return t("nav.certificates");
  return t("nav.files");
}

function typeIcon(type: SearchResult["type"]): string {
  if (type === "article") return "✎";
  if (type === "certificate") return "◎";
  return "▣";
}

export function SearchResultCard({
  result,
  onSelect,
}: {
  result: SearchResult;
  onSelect: (result: SearchResult) => void;
}) {
  const { t } = useTranslation();

  return (
    <button type="button" className="search-result-card" onClick={() => onSelect(result)}>
      <div className="search-result-card-head">
        <span className="search-result-type-icon" aria-hidden="true">
          {typeIcon(result.type)}
        </span>
        <div className="search-result-card-copy">
          <strong>{result.title}</strong>
          <span className="muted">{typeLabel(result.type, t)}</span>
        </div>
        <div className="search-result-badges">
          {result.type === "article" && result.status ? (
            <ArticleStatusBadge status={result.status as Article["status"]} />
          ) : null}
          {result.type === "certificate" && result.status ? (
            <CertificateStatusBadge status={result.status as Certificate["status"]} />
          ) : null}
        </div>
      </div>
      {result.snippet ? <p className="muted search-result-snippet">{result.snippet}</p> : null}
    </button>
  );
}

export function SearchResultList({
  results,
  onSelect,
  emptyMessage,
}: {
  results: SearchResult[];
  onSelect: (result: SearchResult) => void;
  emptyMessage?: string;
}) {
  const { t } = useTranslation();

  if (results.length === 0) {
    return <p className="muted search-empty-inline">{emptyMessage ?? t("search.noResults")}</p>;
  }

  return (
    <div className="search-result-list">
      {results.map((result) => (
        <SearchResultCard key={`${result.type}-${result.id}`} result={result} onSelect={onSelect} />
      ))}
    </div>
  );
}
