import NextAuth from "next-auth";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { db } from "@/lib/db";
import { accounts, sessions, users, verificationTokens } from "@/lib/db/schema";
import { mayAccess, normalizeEmail } from "@/lib/access";
import { sendSignInLink } from "@/lib/mail";

const DAY = 24 * 60 * 60;

// Sign-in links are built from AUTH_URL. Pin it to the portal's public address so a forged
// Host header can never point a link at another site.
// Assigning undefined to process.env stores the string "undefined", which breaks every auth
// request, so only copy APP_URL when it is set.
if (process.env.APP_URL) process.env.AUTH_URL ??= process.env.APP_URL;

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: DrizzleAdapter(db, {
    usersTable: users,
    accountsTable: accounts,
    sessionsTable: sessions,
    verificationTokensTable: verificationTokens,
  }),
  // Spec 15: database sessions with a 30-day rolling expiry.
  session: { strategy: "database", maxAge: 30 * DAY, updateAge: DAY },
  providers: [
    {
      id: "email",
      type: "email",
      name: "Email",
      from: process.env.EMAIL_FROM ?? "Trading desk <alerts@example.com>",
      maxAge: 15 * 60, // links expire after 15 minutes and work once
      normalizeIdentifier: normalizeEmail,
      sendVerificationRequest: ({ identifier, url }) => sendSignInLink(identifier, url),
      options: {},
    },
  ],
  pages: { signIn: "/sign-in", verifyRequest: "/sign-in?sent=1", error: "/sign-in" },
  callbacks: {
    // Checked when the link is requested and again when it is used.
    async signIn({ user }) {
      return !!user.email && (await mayAccess(user.email));
    },
  },
  trustHost: true,
});
