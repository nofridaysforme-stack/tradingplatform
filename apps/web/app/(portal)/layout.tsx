import { redirect } from "next/navigation";
import { BottomTabs, SideNav } from "@/components/nav";
import { requireUser } from "@/lib/session";

export default async function PortalLayout({ children }: LayoutProps<"/">) {
  const user = await requireUser();
  if (!user.acknowledgedNoticeAt) redirect("/notice");
  return (
    <div className="flex min-h-dvh bg-bg lg:bg-page">
      <SideNav />
      <div className="min-w-0 flex-1 pb-[calc(64px+env(safe-area-inset-bottom))] lg:pb-0">
        <div className="mx-auto min-h-dvh max-w-[1080px] bg-bg">{children}</div>
      </div>
      <BottomTabs />
    </div>
  );
}
