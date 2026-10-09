"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { setForex, type ForexState } from "./actions";

/** Admin control for the forex switch. Pausing hides the forex pages and stops the forex
 *  scans; resuming brings everything back as it was. */
export function ForexSwitch({ enabled }: { enabled: boolean }) {
  const [state, onSubmit, pending] = useFormAction<ForexState>(setForex, {});
  return (
    <form onSubmit={onSubmit} aria-label="Forex" className="flex flex-col gap-2">
      <p className="m-0 max-w-[62ch] text-[13px] text-mute">
        {enabled
          ? "Forex is on. Pausing stops the forex scans and alerts and hides the forex pages. Nothing is deleted."
          : "Forex is paused. The forex scans and alerts are off and the forex pages are hidden. Resuming brings everything back as it was."}
      </p>
      <input type="hidden" name="forex" value={enabled ? "pause" : "resume"} />
      {state.error && (
        <p role="alert" className="m-0 text-[13px] text-error">
          {state.error}
        </p>
      )}
      {state.ok && (
        <p role="status" className="m-0 text-sm font-medium text-ink">
          {state.message}
        </p>
      )}
      <div>
        <Button kind="secondary" type="submit" disabled={pending}>
          {enabled ? "Pause forex" : "Resume forex"}
        </Button>
      </div>
    </form>
  );
}
