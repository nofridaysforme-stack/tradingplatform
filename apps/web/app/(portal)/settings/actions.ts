"use server";

import { cookies } from "next/headers";
import { signOut } from "@/lib/auth";
import { requireUser } from "@/lib/session";
import { parseTheme, THEME_COOKIE } from "@/lib/theme";

export async function setTheme(form: FormData): Promise<void> {
  await requireUser();
  const theme = parseTheme(String(form.get("theme")));
  (await cookies()).set(THEME_COOKIE, theme, {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    httpOnly: true,
    maxAge: 365 * 24 * 60 * 60,
  });
}

export async function signOutAction(): Promise<void> {
  await signOut({ redirectTo: "/sign-in" });
}
