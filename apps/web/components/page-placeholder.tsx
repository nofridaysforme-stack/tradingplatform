import { IndicatorRing } from "@/components/ring";

const EMPTY = Array(8).fill("off") as "off"[];

/** Holds a nav destination until its page is built, so links never lead to a 404. */
export function PagePlaceholder({ title }: { title: string }) {
  return (
    <main>
      <header className="px-5 pt-6 pb-3.5">
        <h1 className="m-0 text-[22px] font-semibold leading-tight">{title}</h1>
      </header>
      <section className="flex flex-col items-center gap-4 border-t border-rule px-5 py-14 text-center">
        <IndicatorRing states={EMPTY} direction="long" size={72} showCount={false} label={title} />
        <p className="m-0 max-w-[280px] text-sm text-ink-2">This page is not built yet.</p>
      </section>
    </main>
  );
}
