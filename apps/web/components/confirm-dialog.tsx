"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui";

/** Handoff dialog: 440 wide, 1px ink border, radius 6, no shadow; Cancel then the action. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirm,
  pending,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirm: string;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="confirm-title"
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      className="m-auto w-[min(440px,calc(100vw-32px))] rounded-dialog border border-ink bg-bg p-0 text-ink backdrop:bg-black/40"
    >
      <div className="px-7 py-6">
        <h2 id="confirm-title" className="m-0 text-lg font-semibold">
          {title}
        </h2>
        <div className="mt-2 text-sm text-ink-2">{children}</div>
        <div className="mt-6 flex justify-end gap-3">
          <Button kind="secondary" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm} disabled={pending} className="h-11 text-sm">
            {confirm}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
