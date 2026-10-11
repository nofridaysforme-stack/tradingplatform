import type { Metadata } from "next";
import { RingMark } from "@/components/ring";
import { Button } from "@/components/ui";

export const metadata: Metadata = { title: "Sign in · Trading desk" };

/**
 * Where a sign-in link made by an admin lands. Opening this page signs nobody in: message
 * apps (iPhone Messages, WhatsApp) open every link to draw a preview, which would use up a
 * one-time link before the person taps it. The sign-in happens only when they press the button.
 */
export default async function ContinueSignInPage({ searchParams }: PageProps<"/sign-in/continue">) {
  const params = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
  const token = one(params.token);
  const email = one(params.email);
  const next = one(params.callbackUrl);
  // Only a path on this site, never another address.
  const callbackUrl = next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
  return (
    <main className="flex min-h-dvh items-start justify-center bg-page px-5 py-16 sm:items-center">
      <div className="w-full max-w-[400px] bg-bg px-6 py-8 sm:border sm:border-rule">
        <div className="mb-8 flex items-center gap-2.5">
          <RingMark size={24} />
          <span className="text-base font-semibold">Trading desk</span>
        </div>
        {token && email ? (
          <form method="get" action="/api/auth/callback/email" className="flex flex-col gap-4">
            <input type="hidden" name="token" value={token} />
            <input type="hidden" name="email" value={email} />
            <input type="hidden" name="callbackUrl" value={callbackUrl} />
            <h1 className="m-0 text-lg font-semibold">Sign in as {email}</h1>
            <p className="m-0 text-sm text-ink-2">This link works once. Press the button to open the portal.</p>
            <Button kind="primary" type="submit">
              Sign in
            </Button>
          </form>
        ) : (
          <p className="m-0 text-sm text-ink-2">This sign-in link is incomplete. Ask the person who sent it for a new one.</p>
        )}
      </div>
    </main>
  );
}
