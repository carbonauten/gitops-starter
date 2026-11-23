import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import {
  createWordPressSitePost,
  fetchWordPressSitePlugins,
  fetchWordPressSitePosts,
  fetchWordPressSiteStatus,
  fetchWordPressSites,
  setWordPressSitePluginStatus,
  type WordPressPlugin,
  type WordPressPost,
  type WordPressSite,
  type WordPressSiteStatus,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

type Tab = "posts" | "plugins";

export function WordPressSiteDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const [site, setSite] = useState<WordPressSite | null>(null);
  const [status, setStatus] = useState<WordPressSiteStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("posts");

  const [posts, setPosts] = useState<WordPressPost[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(false);
  const [postsError, setPostsError] = useState("");

  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newStatus, setNewStatus] = useState("draft");
  const [creatingPost, setCreatingPost] = useState(false);
  const [createError, setCreateError] = useState("");

  const [plugins, setPlugins] = useState<WordPressPlugin[]>([]);
  const [loadingPlugins, setLoadingPlugins] = useState(false);
  const [pluginsError, setPluginsError] = useState("");
  const [togglingPlugin, setTogglingPlugin] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      setLoading(true);
      try {
        const sites = await fetchWordPressSites();
        setSite(sites.find((candidate) => candidate.id === id) ?? null);
        setStatus(await fetchWordPressSiteStatus(id));
      } catch (err) {
        setStatusError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function reloadPosts() {
    if (!id) return;
    setLoadingPosts(true);
    setPostsError("");
    try {
      setPosts(await fetchWordPressSitePosts(id));
    } catch (err) {
      setPostsError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoadingPosts(false);
    }
  }

  async function reloadPlugins() {
    if (!id) return;
    setLoadingPlugins(true);
    setPluginsError("");
    try {
      setPlugins(await fetchWordPressSitePlugins(id));
    } catch (err) {
      setPluginsError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoadingPlugins(false);
    }
  }

  useEffect(() => {
    if (!id || loading) return;
    if (tab === "posts" && posts.length === 0 && !loadingPosts && !postsError) void reloadPosts();
    if (tab === "plugins" && plugins.length === 0 && !loadingPlugins && !pluginsError) void reloadPlugins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, loading]);

  async function handleCreatePost(event: FormEvent) {
    event.preventDefault();
    if (!id) return;
    setCreatingPost(true);
    setCreateError("");
    try {
      await createWordPressSitePost(id, { title: newTitle, content: newContent, status: newStatus });
      setNewTitle("");
      setNewContent("");
      setNewStatus("draft");
      await reloadPosts();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setCreatingPost(false);
    }
  }

  async function handleTogglePlugin(plugin: WordPressPlugin) {
    if (!id) return;
    setTogglingPlugin(plugin.plugin);
    try {
      const nextStatus = plugin.status === "active" ? "inactive" : "active";
      await setWordPressSitePluginStatus(id, plugin.plugin, nextStatus);
      await reloadPlugins();
    } catch (err) {
      setPluginsError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setTogglingPlugin(null);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">
          <Link to="/wordpress">{t("wordpressSites.backToSites")}</Link>
        </p>
        <h1>{t("wordpressSites.detailTitle", { label: site?.label || id })}</h1>
        <p className="muted">{site?.base_url}</p>
      </header>

      {loading ? <LoadingState /> : null}
      {statusError ? <p className="error-text">{statusError}</p> : null}
      {status ? (
        <p className="success-text">{t("wordpressSites.statusOk", { user: status.connected_as })}</p>
      ) : null}

      {!loading ? (
        <>
          <div className="drawer-tabs" style={{ marginBottom: 16 }}>
            <button
              type="button"
              className={tab === "posts" ? "primary-button" : "ghost-button"}
              onClick={() => setTab("posts")}
            >
              {t("wordpressSites.tabPosts")}
            </button>
            <button
              type="button"
              className={tab === "plugins" ? "primary-button" : "ghost-button"}
              onClick={() => setTab("plugins")}
            >
              {t("wordpressSites.tabPlugins")}
            </button>
          </div>

          {tab === "posts" ? (
            <>
              <div className="integration-connect-block">
                <div className="integration-connect-header">
                  <strong>{t("wordpressSites.newPostTitle")}</strong>
                </div>
                <form className="entra-setup-form" onSubmit={(event) => void handleCreatePost(event)}>
                  <label>
                    {t("wordpressSites.postTitlePh")}
                    <input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} required autoComplete="off" />
                  </label>
                  <label>
                    {t("wordpressSites.postContentPh")}
                    <textarea
                      value={newContent}
                      onChange={(event) => setNewContent(event.target.value)}
                      rows={6}
                      style={{ width: "100%", fontFamily: "inherit" }}
                    />
                  </label>
                  <label>
                    {t("wordpressSites.postStatus")}
                    <select value={newStatus} onChange={(event) => setNewStatus(event.target.value)}>
                      <option value="draft">{t("wordpressSites.statusDraft")}</option>
                      <option value="publish">{t("wordpressSites.statusPublish")}</option>
                      <option value="pending">{t("wordpressSites.statusPending")}</option>
                      <option value="private">{t("wordpressSites.statusPrivate")}</option>
                    </select>
                  </label>
                  {createError ? <p className="error-text">{createError}</p> : null}
                  <button type="submit" className="primary-button" disabled={creatingPost}>
                    {creatingPost ? t("common.loading") : t("wordpressSites.createPost")}
                  </button>
                </form>
              </div>

              {postsError ? <p className="error-text">{postsError}</p> : null}
              {loadingPosts ? <LoadingState /> : null}
              {!loadingPosts && !postsError && posts.length === 0 ? (
                <EmptyState message={t("wordpressSites.postsEmpty")} icon="✎" />
              ) : null}
              <div className="list-stack">
                {!loadingPosts
                  ? posts.map((post) => (
                      <article key={post.id} className="list-card">
                        <div>
                          <h2>{post.title || "—"}</h2>
                          <p className="muted">{post.status}</p>
                        </div>
                        {post.link ? (
                          <a className="ghost-button" href={post.link} target="_blank" rel="noreferrer">
                            {t("wordpress.openSite")}
                          </a>
                        ) : null}
                      </article>
                    ))
                  : null}
              </div>
            </>
          ) : null}

          {tab === "plugins" ? (
            <>
              {pluginsError ? <p className="error-text">{pluginsError}</p> : null}
              {loadingPlugins ? <LoadingState /> : null}
              {!loadingPlugins && !pluginsError && plugins.length === 0 ? (
                <EmptyState message={t("wordpressSites.pluginsEmpty")} icon="▣" />
              ) : null}
              <div className="list-stack">
                {!loadingPlugins
                  ? plugins.map((plugin) => (
                      <article key={plugin.plugin} className="list-card">
                        <div>
                          <h2>{plugin.name}</h2>
                          <p className="muted">
                            {plugin.version} · {plugin.status}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={togglingPlugin === plugin.plugin}
                          onClick={() => void handleTogglePlugin(plugin)}
                        >
                          {plugin.status === "active" ? t("wordpressSites.pluginDeactivate") : t("wordpressSites.pluginActivate")}
                        </button>
                      </article>
                    ))
                  : null}
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
