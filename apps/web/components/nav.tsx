"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RingMark } from "@/components/ring";
import { cn } from "@/lib/utils";

// Design handoff, Navigation: five tabs on mobile, the full list on desktop. Forex pages
// (marked forex) are left out while forex is paused (decision 2026-10-08).
interface Item {
  href: string;
  label: string;
  forex?: true;
}
const MOBILE: Item[] = [
  { href: "/dashboard", label: "Signals", forex: true },
  { href: "/levels", label: "Levels", forex: true },
  { href: "/stocks", label: "Stocks" },
  { href: "/history", label: "History", forex: true },
  { href: "/holdings", label: "Holdings" },
  { href: "/settings", label: "Settings" },
];
const DESKTOP: Item[] = [
  { href: "/dashboard", label: "Signals", forex: true },
  { href: "/levels", label: "Levels", forex: true },
  { href: "/stocks", label: "Stocks" },
  { href: "/holdings", label: "Holdings" },
  { href: "/history", label: "History", forex: true },
  { href: "/econ", label: "Econ events", forex: true },
  { href: "/health", label: "Health" },
  { href: "/settings", label: "Settings" },
];
const MOBILE_TABS = 5;

/** The items to show: forex pages only while forex is on. On mobile, Holdings takes a tab
 *  only when the forex tabs are gone. */
export function navItems(forex: boolean, mobile: boolean): Item[] {
  const items = (mobile ? MOBILE : DESKTOP).filter((i) => forex || !i.forex);
  return mobile ? items.filter((i) => i.href !== "/holdings" || items.length <= MOBILE_TABS) : items;
}

const COLS: Record<number, string> = { 3: "grid-cols-3", 4: "grid-cols-4", 5: "grid-cols-5" };

function useActive() {
  const path = usePathname();
  return (href: string) => path === href || path.startsWith(`${href}/`) || (href === "/dashboard" && path.startsWith("/signals"));
}

export function SideNav({ forex }: { forex: boolean }) {
  const active = useActive();
  const home = forex ? "/dashboard" : "/stocks";
  return (
    <nav aria-label="Main" className="sticky top-0 hidden h-dvh w-[200px] flex-none flex-col border-r border-rule bg-bg lg:flex">
      <Link href={home} className="flex items-center gap-2.5 px-5 pt-6 pb-6 text-sm font-semibold text-ink no-underline">
        <RingMark size={24} />
        Trading desk
      </Link>
      <ul className="m-0 flex list-none flex-col p-0">
        {navItems(forex, false).map(({ href, label }) => {
          const on = active(href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "flex h-10 items-center border-l-2 px-[18px] text-sm no-underline",
                  on ? "border-ink font-semibold text-ink" : "border-transparent text-ink-2 hover:text-ink",
                )}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function BottomTabs({ forex }: { forex: boolean }) {
  const active = useActive();
  const items = navItems(forex, true);
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-10 border-t border-rule bg-bg pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className={cn("m-0 grid h-16 list-none p-0", COLS[items.length] ?? "grid-cols-5")}>
        {items.map(({ href, label }) => {
          const on = active(href);
          return (
            <li key={href} className="flex">
              <Link
                href={href}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "flex flex-1 flex-col items-center justify-center gap-1.5 text-xs no-underline",
                  on ? "font-semibold text-ink" : "text-mute",
                )}
              >
                <span aria-hidden="true" className={cn("h-0.5 w-[18px]", on ? "bg-ink" : "bg-transparent")} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
