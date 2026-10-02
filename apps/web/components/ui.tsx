// Primitives from the design handoff (section 3). Ruled, not carded: no shadows, 1px rules,
// radius 4 on controls, 3 on badges.
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type ButtonKind = "primary" | "secondary" | "inline";

export function Button({
  kind = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-control font-medium disabled:opacity-60",
        kind === "primary" && "h-12 bg-ink px-5 text-[15px] font-semibold text-bg",
        kind === "secondary" && "h-11 border border-rule bg-transparent px-4 text-sm text-ink",
        kind === "inline" &&
          "relative h-8 border border-rule bg-transparent px-3 text-[13px] text-ink after:absolute after:-inset-y-1.5 after:inset-x-0 after:content-['']",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  id,
  label,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; error?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label htmlFor={id} className="text-sm text-ink-2">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(
          "h-12 rounded-control border bg-input px-3.5 text-base text-ink outline-none",
          error ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink",
        )}
        {...props}
      />
      {error && (
        <p id={`${id}-error`} className="text-[13px] text-error">
          {error}
        </p>
      )}
    </div>
  );
}

export function Badge({ kind, children }: { kind: "provisional" | "confluence" | "state"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-block rounded-badge border px-1.5 py-px text-xs leading-[1.4]",
        kind === "provisional" ? "border-dashed border-prov text-prov" : "border-ink text-ink",
      )}
    >
      {children}
    </span>
  );
}

export function ProvisionalBadge() {
  return <Badge kind="provisional">Provisional</Badge>;
}

export function DirectionMarker({ direction, large = false }: { direction: "long" | "short"; large?: boolean }) {
  const long = direction === "long";
  return (
    <span className={cn("font-semibold", large ? "text-[17px]" : "text-sm", long ? "text-long" : "text-short-ink")}>
      <span aria-hidden="true">{long ? "▲" : "▼"}</span> {long ? "Long" : "Short"}
    </span>
  );
}

export function Rule({ className }: { className?: string }) {
  return <hr className={cn("m-0 border-0 border-t border-rule", className)} />;
}
