// Points the Telegram bot at this portal's webhook (spec 11): POST {APP_URL}/api/telegram/webhook/
// {TELEGRAM_WEBHOOK_SECRET}, with the same secret as the secret-token header. Idempotent; runs
// after migrations on each web deploy, so a new domain or secret takes effect by redeploying.
// Skips when the bot is not set up. A Telegram failure is reported but never fails the deploy.
// The bot token is part of the request URL, so no URL or raw error is ever printed.

const token = process.env.TELEGRAM_BOT_TOKEN?.trim();
const secret = process.env.TELEGRAM_WEBHOOK_SECRET?.trim();
const appUrl = process.env.APP_URL?.trim().replace(/\/+$/, "");

if (!token || !secret || !appUrl) {
  console.log("telegram-webhook: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, or APP_URL not set, skipping");
  process.exit(0);
}
if (!/^[A-Za-z0-9_-]{16,256}$/.test(secret)) {
  // Telegram allows only these characters in the secret-token header.
  console.error("telegram-webhook: TELEGRAM_WEBHOOK_SECRET must be 16 to 256 letters, digits, _ or -");
  process.exit(0);
}
if (!appUrl.startsWith("https://")) {
  console.error("telegram-webhook: APP_URL must start with https:// (Telegram only calls HTTPS webhooks)");
  process.exit(0);
}

async function call(method, body) {
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      signal: AbortSignal.timeout(10_000),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok && data.ok === true, status: res.status, result: data.result, description: data.description };
  } catch {
    return { ok: false, status: 0, description: "could not reach Telegram" };
  }
}

const set = await call("setWebhook", {
  url: `${appUrl}/api/telegram/webhook/${secret}`,
  secret_token: secret,
  allowed_updates: ["message"],
});
if (!set.ok) {
  const why = set.status === 401 || set.status === 404 ? "the bot token was rejected" : set.description ?? `HTTP ${set.status}`;
  console.error(`telegram-webhook: not registered (${why})`);
  process.exit(0);
}
const info = await call("getWebhookInfo");
const pending = info.result?.pending_update_count ?? 0;
const lastError = info.result?.last_error_message;
console.log(`telegram-webhook: registered for ${appUrl}, ${pending} pending updates`);
if (lastError) console.log(`telegram-webhook: Telegram's last delivery error was "${lastError}"`);
