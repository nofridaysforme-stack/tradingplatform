// The health alert the web service sends when the scanner itself has stopped (spec 11). Same
// wording, layout, and footer as the scanner's messages (services/scanner/scanner/notify/
// messages.py), so an admin can't tell which service sent it.

export interface AlertMessage {
  title: string;
  body: string;
  url: string;
}

export const HEARTBEAT_CONDITION = "heartbeat_stale";

export function heartbeatAlert(baseUrl: string): AlertMessage {
  return {
    title: "Health alert: scanner heartbeat is late",
    body: "The scanner has not reported for over 5 minutes.",
    url: `${baseUrl.replace(/\/+$/, "")}/health`,
  };
}

/** Telegram and the email plain-text part. */
export function messageText(m: AlertMessage): string {
  return [m.title, "", m.body, ...(m.url ? ["", m.url] : [])].join("\n");
}

const escape = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");

/** Email HTML: ink on ledger, ruled, no images (spec 13 tokens). */
export function messageHtml(m: AlertMessage): string {
  const lines = m.body
    .split("\n")
    .filter(Boolean)
    .map((line) => `<p style='margin:0 0 8px'>${escape(line)}</p>`)
    .join("");
  const link = m.url
    ? `<p style='margin:16px 0 0'><a href='${escape(m.url)}' style='color:#2563C9'>Open in the portal</a></p>`
    : "";
  return (
    "<!doctype html><html><body style='margin:0;padding:24px;background:#F6F7F5;" +
    "color:#23282E;font:15px/1.5 IBM Plex Sans,Helvetica,Arial,sans-serif'>" +
    "<div style='max-width:560px;border-top:1px solid #C9CED3;padding-top:16px'>" +
    `<h1 style='font-size:18px;margin:0 0 12px'>${escape(m.title)}</h1>` +
    `${lines}${link}<p style='margin:24px 0 0;color:#5A626B;font-size:13px'>` +
    "Trading desk suggests trades from your own rules. It does not place trades. " +
    "Every decision is yours.</p></div></body></html>"
  );
}
