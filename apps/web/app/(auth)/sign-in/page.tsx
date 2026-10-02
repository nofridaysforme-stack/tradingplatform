import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { RingMark } from "@/components/ring";
import { auth } from "@/lib/auth";
import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = { title: "Sign in · Trading desk" };

const ERRORS: Record<string, string> = {
  AccessDenied: "This email isn't approved. Ask an admin to add it.",
  Verification: "That sign-in link has expired or was already used. Ask for a new one.",
  inactive: "This account has been deactivated. Ask an admin for access.",
};

export default async function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  const session = await auth();
  if (session?.user) redirect("/dashboard");
  const params = await searchParams;
  const error = typeof params.error === "string" ? (ERRORS[params.error] ?? "Sign-in didn't work. Try again.") : undefined;
  return (
    <main className="flex min-h-dvh items-start justify-center bg-page px-5 py-16 sm:items-center">
      <div className="w-full max-w-[400px] bg-bg px-6 py-8 sm:border sm:border-rule">
        <div className="mb-8 flex items-center gap-2.5">
          <RingMark size={24} />
          <span className="text-base font-semibold">Trading desk</span>
        </div>
        <SignInForm initial={{ sent: params.sent === "1", error }} />
      </div>
    </main>
  );
}
