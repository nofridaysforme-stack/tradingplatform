import type { Metadata } from "next";
import { RingMark } from "@/components/ring";
import { Button } from "@/components/ui";
import { NOTICE } from "@/lib/notice";
import { requireUser } from "@/lib/session";
import { acknowledgeNotice } from "./actions";

export const metadata: Metadata = { title: "Before you start · Trading desk" };

export default async function NoticePage() {
  await requireUser();
  return (
    <main className="flex min-h-dvh items-start justify-center bg-page px-5 py-16 sm:items-center">
      <div className="w-full max-w-[480px] bg-bg px-6 py-8 sm:border sm:border-rule">
        <div className="mb-6 flex items-center gap-2.5">
          <RingMark size={24} />
          <span className="text-base font-semibold">Trading desk</span>
        </div>
        <h1 className="mb-3 text-[22px] font-semibold leading-tight">Before you start</h1>
        <p className="mb-8 text-[15px] leading-normal text-ink-2">{NOTICE}</p>
        <form action={acknowledgeNotice}>
          <Button type="submit" className="w-full">
            I understand
          </Button>
        </form>
      </div>
    </main>
  );
}
