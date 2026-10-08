import { redirect } from "next/navigation";
import { BottomTabs, SideNav } from "@/components/nav";
import { Providers } from "@/components/providers";
import { forexEnabled } from "@/lib/app-settings";
import { requireUser } from "@/lib/session";

export default async function PortalLayout({ children }: LayoutProps<"/">) {
  const user = await requireUser();
  if (!user.acknowledgedNoticeAt) redirect("/notice");
  const forex = await forexEnabled();
  return (
    <div className="flex min-h-dvh bg-bg lg:bg-page">
      <SideNav forex={forex} />
      <div className="min-w-0 flex-1 pb-[calc(64px+env(safe-area-inset-bottom))] lg:pb-0">
        <div className="mx-auto min-h-dvh max-w-[1080px] bg-bg">
          <Providers>{children}</Providers>
        </div>
      </div>
      <BottomTabs forex={forex} />
    </div>
  );
}
