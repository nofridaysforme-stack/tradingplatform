import "server-only";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { Resend } from "resend";

export class EmailNotConfiguredError extends Error {}

/**
 * Sends the sign-in link. With AUTH_TEST_MAILBOX set (tests and local development) the link
 * is written to <mailbox>/<email>.json instead of being emailed. Links are never logged
 * (spec 15). Without Resend or a test mailbox, sign-in is unavailable.
 */
export async function sendSignInLink(email: string, url: string): Promise<void> {
  const mailbox = process.env.AUTH_TEST_MAILBOX;
  if (mailbox) {
    await mkdir(mailbox, { recursive: true });
    await writeFile(path.join(mailbox, `${email}.json`), JSON.stringify({ email, url, at: new Date().toISOString() }));
    return;
  }
  const key = process.env.RESEND_API_KEY;
  const from = process.env.EMAIL_FROM;
  if (!key || !from) throw new EmailNotConfiguredError("Email is not set up yet");
  const { error } = await new Resend(key).emails.send({
    from,
    to: email,
    subject: "Your sign-in link for Trading desk",
    text: `Sign in to Trading desk:\n\n${url}\n\nThis link works once and expires in 15 minutes. If you didn't ask for it, ignore this email.`,
  });
  if (error) throw new Error(`Resend rejected the email: ${error.name}`);
}
