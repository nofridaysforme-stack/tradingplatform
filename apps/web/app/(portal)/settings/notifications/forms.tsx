"use client";

import { useState } from "react";
import { Button, Toggle } from "@/components/ui";
import { useFormAction } from "@/lib/use-form-action";
import {
  disconnectTelegram,
  savePrefs,
  sendTestNotification,
  type PrefsState,
} from "./actions";

export interface PrefsValues {
  webpush: boolean;
  telegram: boolean;
  strategies: string[];
  instrumentIds: string[] | null;
  quietStart: string | null;
  quietEnd: string | null;
  includeUpdates: boolean;
}

const STRATEGY_LABELS: [string, string][] = [
  ["three_eight", "3/8 system signals"],
  ["fib_pivot", "Fib Pivot signals"],
  ["stocks", "Stock digest and holdings"],
];
const FOREX_STRATEGIES = new Set(["three_eight", "fib_pivot"]);

export function PrefsForm({
  values,
  pairs,
  telegramLinked,
  forex = true,
}: {
  values: PrefsValues;
  pairs: { id: string; symbol: string }[];
  telegramLinked: boolean;
  /** While forex is paused its choices are hidden but kept, so resuming restores them. */
  forex?: boolean;
}) {
  const [state, onSubmit, pending] = useFormAction<PrefsState>(savePrefs, {});
  const [some, setSome] = useState(
    values.instrumentIds !== null && values.instrumentIds.length > 0,
  );
  const [quiet, setQuiet] = useState(values.quietStart !== null);
  const e = state.fieldErrors ?? {};
  const time = (
    name: "quietStart" | "quietEnd",
    label: string,
    value: string | null,
  ) => (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`prefs-${name}`} className="text-[13px] text-ink-2">
        {label}
      </label>
      <input
        id={`prefs-${name}`}
        name={name}
        type="time"
        defaultValue={value ?? (name === "quietStart" ? "22:00" : "07:00")}
        aria-invalid={e[name] ? true : undefined}
        aria-describedby={e[name] ? `prefs-${name}-error` : undefined}
        className={`h-11 rounded-control border bg-input px-3 text-base text-ink ${e[name] ? "border-[1.5px] border-error" : "border-rule"}`}
      />
      {e[name] && (
        <span id={`prefs-${name}-error`} className="text-[13px] text-error">
          {e[name]}
        </span>
      )}
    </div>
  );
  return (
    <form
      onSubmit={onSubmit}
      aria-label="Notification settings"
      className="flex flex-col gap-5"
    >
      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 text-sm font-semibold">Channels</legend>
        <Toggle
          name="webpush"
          label="Push notifications"
          hint="On the devices where you turned them on"
          defaultChecked={values.webpush}
        />
        <Toggle
          name="telegram"
          label="Telegram"
          hint={telegramLinked ? "Connected" : "Connect Telegram below first"}
          defaultChecked={values.telegram && telegramLinked}
          disabled={!telegramLinked}
        />
        <div className="flex min-h-11 items-center justify-between gap-4 border-b border-rule-faint py-2">
          <span className="flex flex-col">
            <span className="text-sm text-ink">Email</span>
            <span className="text-[13px] text-mute">
              Always on, so nothing important is missed
            </span>
          </span>
          <span className="text-[13px] text-ink-2">On</span>
        </div>
      </fieldset>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 text-sm font-semibold">What to send</legend>
        {!forex &&
          values.strategies
            .filter((v) => FOREX_STRATEGIES.has(v))
            .map((v) => <input key={v} type="hidden" name="strategies" value={v} />)}
        {STRATEGY_LABELS.filter(([value]) => forex || !FOREX_STRATEGIES.has(value)).map(([value, label]) => (
          <label
            key={value}
            className="flex min-h-11 items-center gap-3 border-b border-rule-faint text-sm"
          >
            <input
              type="checkbox"
              name="strategies"
              value={value}
              defaultChecked={values.strategies.includes(value)}
              className="size-4 accent-[var(--ink)]"
            />
            {label}
          </label>
        ))}
        <Toggle
          name="includeUpdates"
          label="Updates"
          hint="Confirmations, resets, and closed trades"
          defaultChecked={values.includeUpdates}
        />
      </fieldset>

      {!forex && (
        <>
          <input type="hidden" name="pairs" value={some ? "some" : "all"} />
          {some &&
            values.instrumentIds?.map((id) => <input key={id} type="hidden" name="instrumentIds" value={id} />)}
        </>
      )}
      {forex && (
        <fieldset
          className="m-0 border-0 p-0"
          aria-describedby={e.pairs ? "prefs-pairs-error" : undefined}
        >
          <legend className="mb-1 text-sm font-semibold">Pairs</legend>
          <label className="flex min-h-11 items-center gap-3 text-sm">
            <input
              type="radio"
              name="pairs"
              value="all"
              defaultChecked={!some}
              onChange={() => setSome(false)}
              className="size-4 accent-[var(--ink)]"
            />
            All pairs
          </label>
          <label className="flex min-h-11 items-center gap-3 text-sm">
            <input
              type="radio"
              name="pairs"
              value="some"
              defaultChecked={some}
              onChange={() => setSome(true)}
              className="size-4 accent-[var(--ink)]"
            />
            Only these pairs
          </label>
          {some && (
            <div className="flex flex-wrap gap-2 pl-7">
              {pairs.map((p) => (
                <label
                  key={p.id}
                  className="relative inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-control border border-rule px-3 text-[13px] has-[:checked]:border-ink has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-long"
                >
                  <input
                    type="checkbox"
                    name="instrumentIds"
                    value={p.id}
                    defaultChecked={values.instrumentIds?.includes(p.id) ?? false}
                    className="peer sr-only"
                  />
                  <span aria-hidden="true" className="hidden peer-checked:inline">
                    ✓
                  </span>
                  {p.symbol}
                </label>
              ))}
            </div>
          )}
          {e.pairs && (
            <p id="prefs-pairs-error" className="m-0 mt-1 text-[13px] text-error">
              {e.pairs}
            </p>
          )}
        </fieldset>
      )}

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 text-sm font-semibold">Quiet hours</legend>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input
            type="checkbox"
            name="quiet"
            checked={quiet}
            onChange={(ev) => setQuiet(ev.currentTarget.checked)}
            className="size-4 accent-[var(--ink)]"
          />
          Don&apos;t send trade alerts during quiet hours
        </label>
        {quiet && (
          <div className="flex flex-wrap gap-4 pl-7">
            {time("quietStart", "From", values.quietStart)}
            {time("quietEnd", "Until", values.quietEnd)}
          </div>
        )}
        <p className="m-0 mt-2 text-[13px] text-mute">
          In your time zone (Settings, Profile). Alerts during quiet hours are
          not sent later, because an old intraday alert can mislead. Signals
          still appear in the portal.
        </p>
      </fieldset>

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
          Save notification settings
        </Button>
      </div>
    </form>
  );
}

export function TelegramControl({
  linked,
  configured,
}: {
  linked: boolean;
  configured: boolean;
}) {
  const [state, onDisconnect, pending] = useFormAction<PrefsState>(
    disconnectTelegram,
    {},
  );
  const [note, setNote] = useState<string | null>(null);
  const connect = async () => {
    setNote(null);
    const res = await fetch("/api/telegram/link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const body = (await res.json().catch(() => ({}))) as {
      url?: string;
      error?: { message: string };
    };
    if (body.url) {
      window.open(body.url, "_blank", "noopener,noreferrer");
      setNote("Telegram opened. Tap Start in the chat, then reload this page.");
    } else
      setNote(
        body.error?.message ?? "Telegram couldn't be connected. Try again.",
      );
  };
  if (linked) {
    return (
      <form
        onSubmit={onDisconnect}
        className="flex flex-wrap items-center gap-3"
      >
        <span className="text-sm text-ink">Connected</span>
        <Button kind="inline" type="submit" disabled={pending}>
          Disconnect Telegram
        </Button>
        {state.ok && (
          <span role="status" className="text-[13px] text-ink-2">
            {state.message}
          </span>
        )}
      </form>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button
          kind="secondary"
          type="button"
          onClick={connect}
          disabled={!configured}
        >
          Connect Telegram
        </Button>
      </div>
      {!configured && (
        <p className="m-0 text-[13px] text-mute">
          Telegram isn&apos;t set up on the server yet.
        </p>
      )}
      {note && (
        <p role="status" className="m-0 text-[13px] text-ink-2">
          {note}
        </p>
      )}
    </div>
  );
}

export function TestButton() {
  const [state, onSubmit, pending] = useFormAction<PrefsState>(
    async () => sendTestNotification(),
    {},
  );
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2">
      <div>
        <Button kind="secondary" type="submit" disabled={pending}>
          Send test notification
        </Button>
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
    </form>
  );
}
