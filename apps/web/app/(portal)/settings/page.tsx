import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Button } from "@/components/ui";
import { NOTICE } from "@/lib/notice";
import { listBrokers } from "@/lib/signals";
import { requireUser } from "@/lib/session";
import { parseTheme, THEME_COOKIE } from "@/lib/theme";
import { setTheme, signOutAction } from "./actions";
import { BrokerChoice } from "./broker-choice";
import { ProfileForm } from "./profile-form";

export const metadata: Metadata = { title: "Settings · Trading desk" };

const ADMIN_LINKS = [
  ["/settings/rules", "Rules", "Parameters, approvals, per-pair overrides, strategy switches"],
  ["/settings/brokers", "Brokers", "Broker profiles, chart links, spreads per pair"],
  ["/settings/pairs", "Pairs", "Forex pairs scanned, pip sizes, order"],
  ["/settings/users", "Users", "Allowlist, roles, deactivate"],
] as const;

const LABELS = { device: "Follow this device", light: "Light", dark: "Dark" } as const;

export default async function SettingsPage() {
  const user = await requireUser();
  const brokers = await listBrokers();
  const theme = parseTheme((await cookies()).get(THEME_COOKIE)?.value);
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">Settings</h1>
        <p className="mt-1 mb-0 text-[13px] text-mute">
          Signed in as {user.email}
          {user.role === "admin" ? " · Admin" : ""}
        </p>
      </header>

      <section aria-labelledby="profile-h" className="border-t border-rule px-5 py-5">
        <h2 id="profile-h" className="mt-0 mb-3 text-[15px] font-semibold">
          Profile
        </h2>
        <ProfileForm name={user.name ?? ""} timezone={user.timezone} zones={Intl.supportedValuesOf("timeZone")} />
      </section>

      <section aria-labelledby="broker-h" className="border-t border-rule px-5 py-5">
        <h2 id="broker-h" className="mt-0 mb-1 text-[15px] font-semibold">
          Broker
        </h2>
        <p className="mt-0 mb-3 text-[13px] text-mute">Signal prices are adjusted by half this broker&apos;s typical spread.</p>
        <BrokerChoice current={user.activeBrokerId} brokers={brokers.map((b) => ({ id: b.id, name: b.name }))} />
      </section>

      {user.role === "admin" && (
        <section aria-labelledby="admin-h" className="border-t border-rule px-5 py-5">
          <h2 id="admin-h" className="mt-0 mb-2 text-[15px] font-semibold">
            Admin
          </h2>
          <ul className="m-0 list-none p-0">
            {ADMIN_LINKS.map(([href, label, hint]) => (
              <li key={href} className="border-b border-rule-faint">
                <Link href={href} className="inline-flex min-h-11 items-center text-sm text-link">
                  {label}
                </Link>
                <span className="ml-2 text-[13px] text-mute">{hint}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="theme-h" className="border-t border-rule px-5 py-5">
        <h2 id="theme-h" className="mt-0 mb-3 text-[15px] font-semibold">
          Theme
        </h2>
        <form action={setTheme} className="flex flex-col gap-4">
          <fieldset className="m-0 flex flex-col border-0 p-0">
            <legend className="sr-only">Theme</legend>
            {(Object.keys(LABELS) as (keyof typeof LABELS)[]).map((value) => (
              <label key={value} className="flex min-h-11 items-center gap-3 border-b border-rule-faint text-sm">
                <input type="radio" name="theme" value={value} defaultChecked={theme === value} className="size-4 accent-[var(--ink)]" />
                {LABELS[value]}
              </label>
            ))}
          </fieldset>
          <Button kind="secondary" type="submit" className="self-start">
            Save theme
          </Button>
        </form>
      </section>

      <section aria-labelledby="notice-h" className="border-t border-rule px-5 py-5">
        <h2 id="notice-h" className="mt-0 mb-2 text-[15px] font-semibold">
          About this portal
        </h2>
        <p className="m-0 max-w-[62ch] text-sm leading-normal text-ink-2">{NOTICE}</p>
      </section>

      <section className="border-t border-rule px-5 py-5">
        <form action={signOutAction}>
          <Button kind="secondary" type="submit">
            Sign out
          </Button>
        </form>
      </section>
    </main>
  );
}
