import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import type { SearchAskResponse, SearchResult, SearchResultType } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { GlobalSearch } from "../components/GlobalSearch";
import { LoadingState } from "../components/LoadingState";
import { SearchResultList } from "../components/SearchResultList";
import { navigateToSearchResult, useDebouncedSearch, useSearchSuggestions } from "../hooks/useSearch";

const FILTERS: Array<SearchResultType | ""> = ["", "article", "file", "certificate"];

export function SearchPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const initialMode = searchParams.get("mode") === "ask" ? "ask" : "search";

  const { query, setQuery, type, setType, data, loading, error, ask } = useDebouncedSearch();
  const { suggestions, aiAvailable } = useSearchSuggestions();
  const [mode, setMode] = useState<"search" | "ask">(initialMode);
  const [askInput, setAskInput] = useState(initialQuery);
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState("");
  const [askResponse, setAskResponse] = useState<SearchAskResponse | null>(null);

  useEffect(() => {
    setQuery(initialQuery);
    setAskInput(initialQuery);
    setMode(initialMode);
  }, [initialQuery, initialMode, setQuery]);

  useEffect(() => {
    const params = new URLSearchParams();
    const activeQuery = mode === "ask" ? askInput.trim() : query.trim();
    if (activeQuery) params.set("q", activeQuery);
    if (mode === "ask") params.set("mode", "ask");
    setSearchParams(params, { replace: true });
  }, [askInput, mode, query, setSearchParams]);

  function handleSelect(result: SearchResult) {
    navigateToSearchResult(result, navigate);
  }

  async function handleAskSubmit(event: FormEvent) {
    event.preventDefault();
    const question = askInput.trim();
    if (question.length < 2) return;
    setAskLoading(true);
    setAskError("");
    try {
      setAskResponse(await ask(question));
    } catch (err) {
      setAskError(err instanceof Error ? err.message : t("common.error"));
      setAskResponse(null);
    } finally {
      setAskLoading(false);
    }
  }

  const results = data?.results ?? [];

  return (
    <section className="page search-page">
      <header className="search-page-hero">
        <p className="eyebrow">{t("search.eyebrow")}</p>
        <h1>{t("search.title")}</h1>
        <p className="muted">{t("search.subtitle")}</p>
        <div className="search-mode-tabs" role="tablist" aria-label={t("search.modeLabel")}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "search"}
            className={mode === "search" ? "admin-tab active" : "admin-tab"}
            onClick={() => setMode("search")}
          >
            {t("search.modeSearch")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "ask"}
            className={mode === "ask" ? "admin-tab active" : "admin-tab"}
            onClick={() => setMode("ask")}
          >
            {aiAvailable ? t("search.modeAskAi") : t("search.modeAsk")}
          </button>
        </div>

        {mode === "search" ? (
          <GlobalSearch variant="hero" autoFocus initialQuery={query} />
        ) : (
          <form className="search-ask-form" onSubmit={(event) => void handleAskSubmit(event)}>
            <textarea
              value={askInput}
              onChange={(event) => setAskInput(event.target.value)}
              placeholder={t("search.askPlaceholder")}
              rows={3}
            />
            <div className="search-ask-actions">
              <button type="submit" className="primary-button" disabled={askLoading || askInput.trim().length < 2}>
                {askLoading ? t("common.loading") : t("search.askSubmit")}
              </button>
              {!aiAvailable ? <p className="muted">{t("search.aiUnavailable")}</p> : null}
            </div>
          </form>
        )}
      </header>

      {suggestions.length > 0 ? (
        <div className="search-suggestions-block search-page-suggestions">
          <p className="search-panel-label">{t("search.suggestions")}</p>
          <div className="search-chip-row">
            {suggestions.map((item) => (
              <button
                key={item}
                type="button"
                className="search-chip"
                onClick={() => {
                  setQuery(item);
                  setAskInput(item);
                  if (mode === "ask") {
                    void (async () => {
                      setAskLoading(true);
                      try {
                        setAskResponse(await ask(item));
                      } finally {
                        setAskLoading(false);
                      }
                    })();
                  }
                }}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {mode === "search" ? (
        <>
          <div className="search-filter-row">
            {FILTERS.map((filter) => (
              <button
                key={filter || "all"}
                type="button"
                className={type === filter ? "search-filter active" : "search-filter"}
                onClick={() => setType(filter)}
              >
                {filter ? t(`search.types.${filter}`) : t("search.types.all")}
                {data?.counts && filter ? ` (${data.counts[filter] ?? 0})` : null}
                {data?.counts && !filter
                  ? ` (${(data.counts.article ?? 0) + (data.counts.file ?? 0) + (data.counts.certificate ?? 0)})`
                  : null}
              </button>
            ))}
          </div>

          {loading ? <LoadingState /> : null}
          {error ? <p className="error-text">{error}</p> : null}
          {!loading && query.trim().length < 2 ? (
            <EmptyState message={t("search.startTyping")} icon="⌕" />
          ) : null}
          {!loading && query.trim().length >= 2 && results.length === 0 ? (
            <EmptyState message={t("search.noResults")} icon="⌕" />
          ) : null}
          {!loading && results.length > 0 ? <SearchResultList results={results} onSelect={handleSelect} /> : null}
        </>
      ) : (
        <>
          {askLoading ? <LoadingState label={t("search.askLoading")} /> : null}
          {askError ? <p className="error-text">{askError}</p> : null}
          {askResponse?.answer ? (
            <article className="search-ai-answer">
              <div className="search-ai-answer-head">
                <h2>{t("search.answerTitle")}</h2>
                <span className={`search-ai-mode search-ai-mode-${askResponse.mode}`}>
                  {askResponse.mode === "ai" ? t("search.aiBadge") : t("search.keywordBadge")}
                </span>
              </div>
              <p>{askResponse.answer}</p>
              {askResponse.search_query !== askResponse.question ? (
                <p className="muted">
                  {t("search.expandedQuery")}: {askResponse.search_query}
                </p>
              ) : null}
            </article>
          ) : null}
          {!askLoading && askResponse && askResponse.results.length === 0 ? (
            <EmptyState message={t("search.noResults")} icon="⌕" />
          ) : null}
          {askResponse?.results.length ? (
            <>
              <h2 className="search-sources-title">{t("search.sourcesTitle")}</h2>
              <SearchResultList results={askResponse.results} onSelect={handleSelect} />
            </>
          ) : null}
          {askResponse?.suggested_queries?.length ? (
            <div className="search-suggestions-block">
              <p className="search-panel-label">{t("search.followUp")}</p>
              <div className="search-chip-row">
                {askResponse.suggested_queries.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="search-chip"
                    onClick={() => {
                      setAskInput(item);
                      void (async () => {
                        setAskLoading(true);
                        try {
                          setAskResponse(await ask(item));
                        } finally {
                          setAskLoading(false);
                        }
                      })();
                    }}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}

      {mode === "search" && data?.counts ? (
        <div className="search-counts card-grid compact-grid">
          <article className="stat-card">
            <p className="stat-label">{t("nav.articles")}</p>
            <p className="stat-value">{data.counts.article ?? 0}</p>
          </article>
          <article className="stat-card">
            <p className="stat-label">{t("nav.files")}</p>
            <p className="stat-value">{data.counts.file ?? 0}</p>
          </article>
          <article className="stat-card">
            <p className="stat-label">{t("nav.certificates")}</p>
            <p className="stat-value">{data.counts.certificate ?? 0}</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}
