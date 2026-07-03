import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import type { SearchResult } from "../api/client";
import { navigateToSearchResult, useSearchSuggestions } from "../hooks/useSearch";
import { searchContent } from "../api/client";
import { SearchResultList } from "./SearchResultList";

type GlobalSearchProps = {
  variant?: "compact" | "hero";
  autoFocus?: boolean;
  initialQuery?: string;
};

export function GlobalSearch({ variant = "compact", autoFocus = false, initialQuery = "" }: GlobalSearchProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [aiAvailable, setAiAvailable] = useState(false);
  const { suggestions } = useSearchSuggestions();

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const payload = await searchContent(trimmed);
          setResults(payload.results.slice(0, 8));
          setAiAvailable(payload.ai_available);
        } catch {
          setResults([]);
        } finally {
          setLoading(false);
        }
      })();
    }, 250);

    return () => window.clearTimeout(timer);
  }, [query]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setOpen(false);
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  function handleSelect(result: SearchResult) {
    setOpen(false);
    navigateToSearchResult(result, navigate);
  }

  const showPanel = open && (query.trim().length > 0 || suggestions.length > 0);
  const rootClass = variant === "hero" ? "global-search global-search-hero" : "global-search global-search-compact";

  return (
    <div className={rootClass} ref={containerRef}>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <div className="global-search-input-wrap">
          <span className="global-search-icon" aria-hidden="true">
            ⌕
          </span>
          <input
            ref={inputRef}
            type="search"
            value={query}
            autoFocus={autoFocus}
            onFocus={() => setOpen(true)}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            placeholder={t("search.placeholder")}
            aria-label={t("search.placeholder")}
          />
          {variant === "compact" ? (
            <kbd className="search-kbd" aria-hidden="true">
              ⌘K
            </kbd>
          ) : null}
        </div>
        {variant === "hero" ? (
          <div className="global-search-hero-actions">
            <button type="submit" className="primary-button">
              {t("search.action")}
            </button>
            <Link
              to={query.trim() ? `/search?q=${encodeURIComponent(query.trim())}&mode=ask` : "/search?mode=ask"}
              className="ghost-button link-button"
              onClick={() => setOpen(false)}
            >
              {t("search.askAi")}
            </Link>
          </div>
        ) : (
          <button type="submit" className="ghost-button global-search-submit">
            {t("search.action")}
          </button>
        )}
      </form>

      {showPanel ? (
        <div className="search-results-panel" role="listbox" aria-label={t("search.resultsTitle")}>
          {loading ? <p className="muted search-panel-status">{t("common.loading")}</p> : null}
          {!loading && query.trim().length >= 2 ? (
            <SearchResultList
              results={results}
              onSelect={handleSelect}
              emptyMessage={t("search.noResults")}
            />
          ) : null}
          {!loading && query.trim().length < 2 && suggestions.length > 0 ? (
            <div className="search-suggestions-block">
              <p className="search-panel-label">{t("search.suggestions")}</p>
              <div className="search-chip-row">
                {suggestions.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="search-chip"
                    onClick={() => {
                      setQuery(item);
                      navigate(`/search?q=${encodeURIComponent(item)}`);
                      setOpen(false);
                    }}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {query.trim().length >= 2 ? (
            <div className="search-panel-footer">
              <Link
                to={`/search?q=${encodeURIComponent(query.trim())}`}
                className="search-panel-link"
                onClick={() => setOpen(false)}
              >
                {t("search.viewAll")}
              </Link>
              <Link
                to={`/search?q=${encodeURIComponent(query.trim())}&mode=ask`}
                className="search-panel-link"
                onClick={() => setOpen(false)}
              >
                {aiAvailable ? t("search.askAi") : t("search.askFallback")}
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
