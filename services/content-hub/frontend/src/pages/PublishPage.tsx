import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  disconnectIntegration,
  fetchArticles,
  fetchIntegrationStatus,
  fetchMicrosoftChannels,
  fetchMicrosoftTeams,
  fetchNotionDatabases,
  fetchPublishChannels,
  fetchPublishHistory,
  fetchPublishSettings,
  integrationConnectUrl,
  publishArticle,
  retryPublicationDelivery,
  runCertificateReminders,
  updatePublishSettings,
  type Article,
  type IntegrationPickerItem,
  type IntegrationStatus,
  type Publication,
  type PublishChannel,
  type PublishSettings,
} from "../api/client";
import { usePermissions } from "../hooks/usePermissions";

const CHANNELS: PublishChannel["channel"][] = ["teams", "outlook", "notion"];

export function PublishPage() {
  const { t } = useTranslation();
  const { isItMaster } = usePermissions();
  const [searchParams, setSearchParams] = useSearchParams();
  const [articles, setArticles] = useState<Article[]>([]);
  const [channels, setChannels] = useState<PublishChannel[]>([]);
  const [history, setHistory] = useState<Publication[]>([]);
  const [settings, setSettings] = useState<PublishSettings | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatus | null>(null);
  const [teams, setTeams] = useState<IntegrationPickerItem[]>([]);
  const [teamChannels, setTeamChannels] = useState<IntegrationPickerItem[]>([]);
  const [notionDatabases, setNotionDatabases] = useState<IntegrationPickerItem[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [selectedArticleId, setSelectedArticleId] = useState("");
  const [selectedChannels, setSelectedChannels] = useState<PublishChannel["channel"][]>([
    "teams",
    "notion",
    "outlook",
  ]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [nextArticles, nextChannels, nextHistory] = await Promise.all([
        fetchArticles(undefined, "published"),
        fetchPublishChannels(),
        fetchPublishHistory(),
      ]);
      setArticles(nextArticles);
      setChannels(nextChannels);
      setHistory(nextHistory);

      let nextSettings: PublishSettings | null = null;
      let nextIntegrationStatus: IntegrationStatus | null = null;
      if (isItMaster) {
        [nextSettings, nextIntegrationStatus] = await Promise.all([
          fetchPublishSettings(),
          fetchIntegrationStatus(),
        ]);
        setSettings(nextSettings);
        setIntegrationStatus(nextIntegrationStatus);
      }

      if (!selectedArticleId && nextArticles[0]) {
        setSelectedArticleId(nextArticles[0].id);
      }

      if (isItMaster && nextIntegrationStatus) {
        if (nextIntegrationStatus.microsoft.connected) {
          const nextTeams = await fetchMicrosoftTeams();
          setTeams(nextTeams);
          const teamId = nextSettings?.teams_team_id || nextTeams[0]?.id || "";
          setSelectedTeamId(teamId);
          if (teamId) {
            setTeamChannels(await fetchMicrosoftChannels(teamId));
          }
        }
        if (nextIntegrationStatus.notion.connected) {
          setNotionDatabases(await fetchNotionDatabases());
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [isItMaster]);

  useEffect(() => {
    const provider = searchParams.get("integration");
    const status = searchParams.get("status");
    if (!provider || !status) {
      return;
    }
    if (status === "success") {
      const providerLabel =
        provider === "microsoft" ? t("publish.microsoftBlockTitle") : t("publish.notionBlockTitle");
      setNotice(t("publish.integrationConnected", { provider: providerLabel }));
    } else {
      const providerLabel =
        provider === "microsoft" ? t("publish.microsoftBlockTitle") : t("publish.notionBlockTitle");
      setError(t("publish.integrationFailed", { provider: providerLabel }));
    }
    setSearchParams({}, { replace: true });
    void load();
  }, [searchParams, setSearchParams, t]);

  function toggleChannel(channel: PublishChannel["channel"]) {
    setSelectedChannels((current) =>
      current.includes(channel) ? current.filter((item) => item !== channel) : [...current, channel],
    );
  }

  async function handlePublish() {
    if (!selectedArticleId || selectedChannels.length === 0) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const publication = await publishArticle(selectedArticleId, selectedChannels);
      setNotice(t("publish.success", { title: publication.title }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry(deliveryId: string) {
    setBusy(true);
    setError("");
    try {
      await retryPublicationDelivery(deliveryId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleCertificateReminders() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await runCertificateReminders();
      setNotice(t("publish.remindersSent", { count: result.reminders_sent }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleTeamChange(teamId: string) {
    setSelectedTeamId(teamId);
    if (!settings) {
      return;
    }
    setSettings({ ...settings, teams_team_id: teamId, teams_channel_id: "" });
    if (teamId) {
      setTeamChannels(await fetchMicrosoftChannels(teamId));
    } else {
      setTeamChannels([]);
    }
  }

  async function handleSettingsSave(event: React.FormEvent) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await updatePublishSettings({
        ...settings,
        teams_enabled: Boolean(settings.teams_team_id && settings.teams_channel_id),
        outlook_enabled: integrationStatus?.microsoft.connected || Boolean(settings.outlook_sender_id),
        notion_enabled: integrationStatus?.notion.connected || Boolean(settings.notion_database_id),
      });
      setSettings(updated);
      setNotice(t("publish.settingsSaved"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect(provider: "microsoft" | "notion") {
    setBusy(true);
    setError("");
    try {
      await disconnectIntegration(provider);
      setNotice(t("publish.integrationDisconnected", {
        provider: provider === "microsoft" ? t("publish.microsoftBlockTitle") : t("publish.notionBlockTitle"),
      }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("publish.title")}</h1>
        <p className="muted">{t("publish.subtitle")}</p>
      </header>

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="invite-notice">{notice}</p> : null}

      {!loading ? (
        <>
          <div className="publish-grid">
            <article className="employee-create-form">
              <h2>{t("publish.articleTitle")}</h2>
              <p className="muted">{t("publish.articleHint")}</p>
              <div className="employee-create-grid">
                <select
                  className="admin-select"
                  value={selectedArticleId}
                  onChange={(event) => setSelectedArticleId(event.target.value)}
                >
                  <option value="">{t("publish.selectArticle")}</option>
                  {articles.map((article) => (
                    <option key={article.id} value={article.id}>
                      {article.title}
                    </option>
                  ))}
                </select>
              </div>

              <h3>{t("publish.channelsTitle")}</h3>
              <div className="publish-channel-list">
                {CHANNELS.map((channel) => {
                  const meta = channels.find((item) => item.channel === channel);
                  return (
                    <label key={channel} className="publish-channel-option">
                      <input
                        type="checkbox"
                        checked={selectedChannels.includes(channel)}
                        disabled={!meta?.available}
                        onChange={() => toggleChannel(channel)}
                      />
                      <span>
                        <strong>{t(`publish.channels.${channel}`)}</strong>
                        <span className="muted">
                          {" "}
                          · {meta?.configured ? t("publish.channelReady") : t("publish.channelMock")}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>

              <button
                type="button"
                className="primary-button"
                disabled={busy || !selectedArticleId || selectedChannels.length === 0}
                onClick={() => void handlePublish()}
              >
                {t("publish.submit")}
              </button>
            </article>

            {isItMaster ? (
              <form className="employee-create-form" onSubmit={(event) => void handleSettingsSave(event)}>
                <h2>{t("publish.settingsTitle")}</h2>
                <p className="muted">{t("publish.settingsHintOAuth")}</p>

                <div className="integration-connect-block">
                  <div className="integration-connect-header">
                    <strong>{t("publish.microsoftBlockTitle")}</strong>
                    {integrationStatus?.microsoft.connected ? (
                      <span className="integration-badge integration-badge-connected">
                        {integrationStatus.microsoft.account || t("publish.connected")}
                      </span>
                    ) : (
                      <span className="integration-badge">{t("publish.notConnected")}</span>
                    )}
                  </div>
                  <p className="muted">{t("publish.microsoftBlockHint")}</p>
                  {integrationStatus?.microsoft.oauth_available ? (
                    integrationStatus.microsoft.connected ? (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={busy}
                        onClick={() => void handleDisconnect("microsoft")}
                      >
                        {t("publish.disconnect")}
                      </button>
                    ) : (
                      <a className="primary-button integration-connect-button" href={integrationConnectUrl("microsoft")}>
                        {t("publish.connectMicrosoft")}
                      </a>
                    )
                  ) : (
                    <p className="muted">{t("publish.microsoftEnvMissing")}</p>
                  )}

                  {integrationStatus?.microsoft.connected && settings ? (
                    <div className="publish-settings-grid">
                      <label className="access-toggle">
                        <input type="checkbox" checked={settings.outlook_enabled} readOnly />
                        <span>{t("publish.channels.outlook")}</span>
                      </label>
                      <p className="muted">{t("publish.outlookAutoConfigured")}</p>
                      <label className="access-toggle">
                        <input
                          type="checkbox"
                          checked={settings.teams_enabled}
                          onChange={(event) =>
                            setSettings({ ...settings, teams_enabled: event.target.checked })
                          }
                        />
                        <span>{t("publish.channels.teams")}</span>
                      </label>
                      <select
                        className="admin-select"
                        value={selectedTeamId}
                        onChange={(event) => void handleTeamChange(event.target.value)}
                      >
                        <option value="">{t("publish.selectTeam")}</option>
                        {teams.map((team) => (
                          <option key={team.id} value={team.id}>
                            {team.name}
                          </option>
                        ))}
                      </select>
                      <select
                        className="admin-select"
                        value={settings.teams_channel_id}
                        onChange={(event) =>
                          setSettings({ ...settings, teams_channel_id: event.target.value })
                        }
                      >
                        <option value="">{t("publish.selectChannel")}</option>
                        {teamChannels.map((channel) => (
                          <option key={channel.id} value={channel.id}>
                            {channel.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                </div>

                <div className="integration-connect-block">
                  <div className="integration-connect-header">
                    <strong>{t("publish.notionBlockTitle")}</strong>
                    {integrationStatus?.notion.connected ? (
                      <span className="integration-badge integration-badge-connected">
                        {integrationStatus.notion.account || t("publish.connected")}
                      </span>
                    ) : (
                      <span className="integration-badge">{t("publish.notConnected")}</span>
                    )}
                  </div>
                  <p className="muted">{t("publish.notionBlockHint")}</p>
                  {integrationStatus?.notion.oauth_available ? (
                    integrationStatus.notion.connected ? (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={busy}
                        onClick={() => void handleDisconnect("notion")}
                      >
                        {t("publish.disconnect")}
                      </button>
                    ) : (
                      <a className="primary-button integration-connect-button" href={integrationConnectUrl("notion")}>
                        {t("publish.connectNotion")}
                      </a>
                    )
                  ) : (
                    <p className="muted">{t("publish.notionEnvMissing")}</p>
                  )}

                  {integrationStatus?.notion.connected && settings ? (
                    <div className="publish-settings-grid">
                      <select
                        className="admin-select"
                        value={settings.notion_database_id}
                        onChange={(event) =>
                          setSettings({
                            ...settings,
                            notion_database_id: event.target.value,
                            notion_enabled: Boolean(event.target.value),
                          })
                        }
                      >
                        <option value="">{t("publish.selectDatabase")}</option>
                        {notionDatabases.map((database) => (
                          <option key={database.id} value={database.id}>
                            {database.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                </div>

                <button type="submit" className="ghost-button" disabled={busy || !settings}>
                  {t("publish.saveSettings")}
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={busy}
                  onClick={() => void handleCertificateReminders()}
                >
                  {t("publish.runReminders")}
                </button>
              </form>
            ) : null}
          </div>

          <div className="admin-table-wrap">
            <h2>{t("publish.historyTitle")}</h2>
            {history.length === 0 ? (
              <p className="muted">{t("publish.empty")}</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{t("publish.history.article")}</th>
                    <th>{t("publish.history.by")}</th>
                    <th>{t("publish.history.channels")}</th>
                    <th>{t("publish.history.when")}</th>
                    <th>{t("departments.columns.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((publication) => (
                    <tr key={publication.id}>
                      <td>
                        <strong>{publication.title}</strong>
                        <div className="muted">{publication.resource_type}</div>
                      </td>
                      <td>{publication.published_by_name}</td>
                      <td>
                        <div className="publish-delivery-list">
                          {publication.deliveries.map((delivery) => (
                            <div key={delivery.id} className="publish-delivery-item">
                              <span>{t(`publish.channels.${delivery.channel}`)}</span>
                              <span className={`publish-status publish-status-${delivery.status}`}>
                                {t(`publish.status.${delivery.status}`)}
                              </span>
                              {delivery.external_url ? (
                                <a href={delivery.external_url} target="_blank" rel="noreferrer">
                                  {t("publish.openLink")}
                                </a>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </td>
                      <td className="muted">{new Date(publication.created_at).toLocaleString()}</td>
                      <td>
                        {publication.deliveries
                          .filter((delivery) => delivery.status === "failed")
                          .map((delivery) => (
                            <button
                              key={delivery.id}
                              type="button"
                              className="ghost-button"
                              disabled={busy}
                              onClick={() => void handleRetry(delivery.id)}
                            >
                              {t("publish.retry")}
                            </button>
                          ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}
