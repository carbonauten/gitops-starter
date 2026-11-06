import { useCallback, useEffect, useRef, useState } from "react";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

type Props = {
  body: string;
  bodyType: "html" | "text";
};

/**
 * Renders untrusted email content inside a sandboxed iframe so embedded
 * <style>/<script>/event-handler payloads can't leak into or execute in the
 * host page. Shared between the Outlook and generic IMAP mailbox viewers -
 * both hand it a plain {body, body_type} regardless of the mail protocol
 * behind it.
 */
const EMAIL_FRAME_BASE_STYLES = `<style>
  html, body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #1f2937;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  img, table, video { max-width: 100%; height: auto; }
  pre { white-space: pre-wrap; }
</style>`;

export function EmailBodyFrame({ body, bodyType }: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(200);

  // The iframe's srcDoc is a separate document, so it does not inherit any
  // of the app's CSS - without this, unstyled email markup (or a plain-text
  // body) falls back to the browser's default UA stylesheet.
  const srcDoc =
    EMAIL_FRAME_BASE_STYLES +
    (bodyType === "html"
      ? body
      : `<pre style="white-space:pre-wrap;font-family:inherit;margin:0">${escapeHtml(body)}</pre>`);

  const resize = useCallback(() => {
    const doc = frameRef.current?.contentDocument;
    if (doc?.body) {
      setHeight(doc.body.scrollHeight + 16);
    }
  }, []);

  useEffect(() => {
    resize();
  }, [srcDoc, resize]);

  return (
    <iframe
      ref={frameRef}
      className="outlook-mail-body outlook-mail-body-frame"
      title="email-body"
      srcDoc={srcDoc}
      sandbox="allow-same-origin allow-popups"
      onLoad={resize}
      style={{ width: "100%", height, border: "none" }}
    />
  );
}
