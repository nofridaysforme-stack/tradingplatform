"use client";

import { Button } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import { saveProfile, type ProfileState } from "./actions";

export function ProfileForm({ name, timezone, zones }: { name: string; timezone: string; zones: string[] }) {
  const [state, onSubmit, pending] = useFormAction<ProfileState>(saveProfile, {});
  const e = state.fieldErrors ?? {};
  return (
    <form onSubmit={onSubmit} noValidate aria-label="Profile" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label htmlFor="profile-name" className="text-sm text-ink-2">
          Name
        </label>
        <input
          id="profile-name"
          name="name"
          defaultValue={name}
          maxLength={80}
          autoComplete="name"
          aria-invalid={e.name ? true : undefined}
          aria-describedby={e.name ? "profile-name-error" : undefined}
          className={`h-12 w-full min-w-0 rounded-control border bg-input px-3.5 text-base text-ink outline-none ${e.name ? "border-[1.5px] border-error" : "border-rule focus:border-[1.5px] focus:border-ink"}`}
        />
        {e.name && (
          <p id="profile-name-error" className="m-0 text-[13px] text-error">
            {e.name}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <label htmlFor="profile-tz" className="text-sm text-ink-2">
          Time zone
        </label>
        <select
          id="profile-tz"
          name="timezone"
          defaultValue={timezone}
          aria-describedby="profile-tz-help"
          className="h-12 w-full min-w-0 rounded-control border border-rule bg-input px-3 text-base text-ink"
        >
          {zones.map((z) => (
            <option key={z} value={z}>
              {z.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <p id="profile-tz-help" className="m-0 text-[13px] text-mute">
          Used for notification quiet hours. Signals and prices always show New York time.
        </p>
        {e.timezone && <p className="m-0 text-[13px] text-error">{e.timezone}</p>}
      </div>
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
          Save profile
        </Button>
      </div>
    </form>
  );
}
