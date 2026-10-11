import { asc, eq } from "drizzle-orm";
import type { Metadata } from "next";
import Link from "next/link";
import { Badge } from "@/components/ui";
import { db } from "@/lib/db";
import { allowlist, users } from "@/lib/db/schema";
import { requireAdmin } from "@/lib/session";
import { AddEmailForm, RemoveEmail, SignInLink, UserControls } from "./forms";

export const metadata: Metadata = { title: "Users · Trading desk" };

export default async function UsersPage() {
  const me = await requireAdmin();
  const rows = await db
    .select({ email: allowlist.email, addedAt: allowlist.addedAt, user: users })
    .from(allowlist)
    .leftJoin(users, eq(users.email, allowlist.email))
    .orderBy(asc(allowlist.email));
  return (
    <main>
      <nav className="px-5 pt-4">
        <Link href="/settings" className="inline-flex min-h-11 items-center text-sm text-link">
          <span aria-hidden="true">‹&nbsp;</span>Settings
        </Link>
      </nav>
      <header className="px-5 pt-1.5 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Users</h1>
        <p className="m-0 mt-1 max-w-[62ch] text-[13px] text-mute">
          Only approved emails can sign in. There is no public sign-up. Admins manage rules, brokers, pairs, and users. If email can&apos;t reach someone yet,
          create a sign-in link and send it to them yourself.
        </p>
      </header>
      <section aria-labelledby="people-h" className="border-t border-rule">
        <h2 id="people-h" className="sr-only">
          Approved emails
        </h2>
        <ul className="m-0 list-none p-0">
          {rows.map(({ email, user }) => (
            <li key={email} className="border-b border-rule-soft px-5 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="min-w-0 text-sm font-semibold break-all">{email}</span>
                {user ? (
                  <>
                    <Badge kind="state">{user.role === "admin" ? "Admin" : "Owner"}</Badge>
                    {!user.active && <span className="text-[13px] text-mute">Deactivated</span>}
                    {user.id === me.id && <span className="text-[13px] text-mute">You</span>}
                  </>
                ) : (
                  <span className="text-[13px] text-mute">Not signed in yet</span>
                )}
              </div>
              {user?.name && <p className="m-0 text-[13px] text-ink-2">{user.name}</p>}
              <div className="mt-2">
                {user ? (
                  <UserControls id={user.id} email={email} role={user.role} active={user.active} self={user.id === me.id} />
                ) : (
                  <RemoveEmail email={email} />
                )}
                {user?.id !== me.id && user?.active !== false && <SignInLink email={email} />}
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="add-h" className="border-t border-rule px-5 py-5">
        <h2 id="add-h" className="m-0 mb-3 text-base font-semibold">
          Approve an email
        </h2>
        <AddEmailForm />
      </section>
    </main>
  );
}
