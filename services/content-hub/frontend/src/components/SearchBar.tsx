import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { searchContent, type SearchResult } from "../api/client";

export function SearchBar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    const items = await searchContent(query.trim());
    setResults(items);
    setOpen(true);
  }

  function openResult(result: SearchResult) {
    setOpen(false);
    if (result.type === "article") {
      navigate(`/articles/${result.id}/edit`);
      return;
    }
    if (result.type === "certificate") {
      navigate(`/certificates/${result.id}/edit`);
      return;
    }
    navigate("/files");
  }

  return (
    <div className="search-bar">
      <form onSubmit={(event) => void handleSubmit(event)}>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search.placeholder")}
        />
        <button type="submit">{t("search.action")}</button>
      </form>
      {open ? (
        <div className="search-results">
          {results.length === 0 ? (
            <p className="muted">{t("search.noResults")}</p>
          ) : (
            results.map((result) => (
              <button key={`${result.type}-${result.id}`} type="button" className="search-result" onClick={() => openResult(result)}>
                <strong>{result.title}</strong>
                <span>
                  {result.type === "article"
                    ? t("nav.articles")
                    : result.type === "certificate"
                      ? t("nav.certificates")
                      : t("nav.files")}
                </span>
                <p className="muted">{result.snippet}</p>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
