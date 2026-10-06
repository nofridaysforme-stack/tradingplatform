"use server";

import { headers } from "next/headers";
import { z } from "zod";
import { EMAIL_LIMIT, emailRequestsInWindow, ipLimiter, mayAccess, normalizeEmail } from "@/lib/access";
import { signIn } from "@/lib/auth";
import { emailConfigured } from "@/lib/mail";

export type SignInState = { sent?: boolean; error?: string; email?: string };

const Email = z.email();

export async function requestSignInLink(_prev: SignInState, form: FormData): Promise<SignInState> {
  const raw = String(form.get("email") ?? "");
  const parsed = Email.safeParse(raw.trim());
  if (!parsed.success) return { error: "Enter an email address, like name@example.com.", email: raw };
  const email = normalizeEmail(parsed.data);

  const h = await headers();
  const ip = (h.get("x-forwarded-for") ?? "").split(",")[0]?.trim() || "local";
  if (!ipLimiter.allow(ip) || (await emailRequestsInWindow(email)) >= EMAIL_LIMIT) {
    return { error: "Too many sign-in links requested. Try again in 15 minutes.", email };
  }
  if (!(await mayAccess(email))) {
    return { error: "This email isn't approved. Ask an admin to add it.", email };
  }
  if (!emailConfigured()) {
    return { error: "Email isn't set up on the server yet, so no link can be sent. An admin needs to add the email settings.", email };
  }
  const failed = { error: "We couldn't send the link. Try again in a minute.", email };
  try {
    // With redirect: false, Auth.js reports a failed send by returning its error page address
    // instead of throwing.
    const to = await signIn("email", { email, redirect: false, redirectTo: "/dashboard" });
    if (typeof to === "string" && new URL(to, "http://local").searchParams.has("error")) return failed;
  } catch {
    return failed;
  }
  return { sent: true, email };
}
