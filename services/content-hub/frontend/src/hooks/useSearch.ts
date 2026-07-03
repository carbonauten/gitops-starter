import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  askSearch,
  fetchSearchSuggestions,
  searchContent,
  type SearchAskResponse,
  type SearchResponse,
  type SearchResultType,
} from "../api/client";

export function useSearchSuggestions() {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [aiAvailable, setAiAvailable] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const payload = await fetchSearchSuggestions();
        setSuggestions(payload.suggestions);
        setAiAvailable(payload.ai_available);
      } catch {
        setSuggestions([]);
      }
    })();
  }, []);

  return { suggestions, aiAvailable };
}

export function useDebouncedSearch(delayMs = 300) {
  const { i18n } = useTranslation();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<SearchResultType | "">("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setData(null);
      setLoading(false);
      setError("");
      return;
    }

    setLoading(true);
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          setError("");
          setData(await searchContent(trimmed, type || undefined));
        } catch (err) {
          setError(err instanceof Error ? err.message : "error");
          setData(null);
        } finally {
          setLoading(false);
        }
      })();
    }, delayMs);

    return () => window.clearTimeout(timer);
  }, [query, type, delayMs]);

  const ask = useCallback(
    async (question: string): Promise<SearchAskResponse> => {
      return askSearch(question, i18n.language, type || undefined);
    },
    [i18n.language, type],
  );

  return {
    query,
    setQuery,
    type,
    setType,
    data,
    loading,
    error,
    ask,
  };
}

export function navigateToSearchResult(
  result: { type: SearchResultType; id: string },
  navigate: (path: string) => void,
) {
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
