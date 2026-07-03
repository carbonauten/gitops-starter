import { FormEvent, useEffect, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createCertificate,
  fetchCertificate,
  fileDownloadUrl,
  requestCertificateRenewal,
  updateCertificate,
  uploadFile,
} from "../api/client";

const CATEGORIES = ["compliance", "product", "training", "ssl"] as const;

function defaultValidFrom(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultValidTo(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() + 1);
  return date.toISOString().slice(0, 10);
}

export function CertificateEditorPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = !id || id === "new";

  const [name, setName] = useState("");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("compliance");
  const [issuer, setIssuer] = useState("");
  const [validFrom, setValidFrom] = useState(defaultValidFrom());
  const [validTo, setValidTo] = useState(defaultValidTo());
  const [renewalInProgress, setRenewalInProgress] = useState(false);
  const [renewalApprovalStatus, setRenewalApprovalStatus] = useState("none");
  const [responsibleName, setResponsibleName] = useState("");
  const [responsibleEmail, setResponsibleEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [fileAssetId, setFileAssetId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isNew || !id) return;
    void (async () => {
      try {
        const certificate = await fetchCertificate(id);
        setName(certificate.name);
        setCategory(certificate.category);
        setIssuer(certificate.issuer);
        setValidFrom(certificate.valid_from);
        setValidTo(certificate.valid_to);
        setRenewalInProgress(certificate.renewal_in_progress);
        setRenewalApprovalStatus(certificate.renewal_approval_status || "none");
        setResponsibleName(certificate.responsible_name);
        setResponsibleEmail(certificate.responsible_email);
        setNotes(certificate.notes);
        setFileAssetId(certificate.file_asset_id);
        setFileName(certificate.file_name);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isNew, t]);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setSaving(true);
    setError("");
    try {
      const uploaded = await uploadFile(file, "certificates");
      setFileAssetId(uploaded.id);
      setFileName(uploaded.original_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
      event.target.value = "";
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const payload = {
      name,
      category,
      issuer,
      valid_from: validFrom,
      valid_to: validTo,
      renewal_in_progress: renewalInProgress,
      responsible_name: responsibleName,
      responsible_email: responsibleEmail,
      file_asset_id: fileAssetId,
      notes,
    };
    try {
      if (isNew) {
        const certificate = await createCertificate(payload);
        navigate(`/certificates/${certificate.id}/edit`, { replace: true });
        return;
      }
      await updateCertificate(id!, payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p>{t("common.loading")}</p>;
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{isNew ? t("certificates.new") : t("certificates.edit")}</h1>
          <p className="muted">{t("certificates.editorSubtitle")}</p>
        </div>
        <Link to="/certificates" className="ghost-button link-button">
          {t("certificates.back")}
        </Link>
      </header>

      <form className="editor-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          {t("certificates.fieldName")}
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>

        <label>
          {t("certificates.fieldCategory")}
          <select value={category} onChange={(event) => setCategory(event.target.value as (typeof CATEGORIES)[number])}>
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {t(`certificates.categories.${item}`)}
              </option>
            ))}
          </select>
        </label>

        <label>
          {t("certificates.fieldIssuer")}
          <input value={issuer} onChange={(event) => setIssuer(event.target.value)} />
        </label>

        <div className="form-grid">
          <label>
            {t("certificates.fieldValidFrom")}
            <input type="date" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} required />
          </label>
          <label>
            {t("certificates.fieldValidTo")}
            <input type="date" value={validTo} onChange={(event) => setValidTo(event.target.value)} required />
          </label>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={renewalInProgress}
            onChange={(event) => setRenewalInProgress(event.target.checked)}
          />
          {t("certificates.fieldRenewal")}
        </label>

        <div className="form-grid">
          <label>
            {t("certificates.fieldResponsibleName")}
            <input value={responsibleName} onChange={(event) => setResponsibleName(event.target.value)} />
          </label>
          <label>
            {t("certificates.fieldResponsibleEmail")}
            <input
              type="email"
              value={responsibleEmail}
              onChange={(event) => setResponsibleEmail(event.target.value)}
            />
          </label>
        </div>

        <label>
          {t("certificates.fieldNotes")}
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} />
        </label>

        <label>
          {t("certificates.fieldFile")}
          <input type="file" accept=".pdf,.pem,.crt,.cer,.txt,image/*" onChange={(event) => void handleFileChange(event)} />
        </label>
        {fileName && fileAssetId ? (
          <p className="muted">
            {t("certificates.attachedFile")}:{" "}
            <a href={fileDownloadUrl(fileAssetId)} target="_blank" rel="noreferrer">
              {fileName}
            </a>
          </p>
        ) : null}

        {error ? <p className="error-text">{error}</p> : null}

        {!isNew && renewalInProgress && renewalApprovalStatus !== "pending" && renewalApprovalStatus !== "approved" ? (
          <div className="form-actions">
            <button
              type="button"
              className="ghost-button"
              disabled={saving}
              onClick={() =>
                void (async () => {
                  setSaving(true);
                  try {
                    await requestCertificateRenewal(id!);
                    setRenewalApprovalStatus("pending");
                  } catch (err) {
                    setError(err instanceof Error ? err.message : t("common.error"));
                  } finally {
                    setSaving(false);
                  }
                })()
              }
            >
              {t("workflow.requestRenewal")}
            </button>
          </div>
        ) : null}

        <div className="form-actions">
          <button type="submit" className="primary-button" disabled={saving}>
            {t("certificates.save")}
          </button>
        </div>
      </form>
    </section>
  );
}
