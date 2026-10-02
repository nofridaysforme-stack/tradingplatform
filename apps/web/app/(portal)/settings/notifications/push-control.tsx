"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui";

type State = "checking" | "unsupported" | "install" | "blocked" | "off" | "on";

const isIos = () =>
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const isInstalled = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true;

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function post(url: string, body: unknown): Promise<boolean> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.ok;
}

/** This device's push subscription (spec 11). Subscribes only after a tap, as Safari requires. */
export function PushControl() {
  const [state, setState] = useState<State>("checking");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      if (
        !("serviceWorker" in navigator) ||
        !("PushManager" in window) ||
        !("Notification" in window)
      ) {
        setState(isIos() && !isInstalled() ? "install" : "unsupported");
        return;
      }
      if (Notification.permission === "denied") return setState("blocked");
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = await reg?.pushManager.getSubscription();
      setState(sub ? "on" : "off");
    })().catch(() => setState("unsupported"));
  }, []);

  const turnOn = async () => {
    setBusy(true);
    setNote(null);
    try {
      const { key } = (await (await fetch("/api/push/public-key")).json()) as {
        key: string | null;
      };
      if (!key) {
        setNote(
          "Push notifications aren't set up on the server yet. Email and Telegram still work.",
        );
        return;
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setState(permission === "denied" ? "blocked" : "off");
        return;
      }
      const reg = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
      });
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(key),
      });
      if (!(await post("/api/push/subscribe", sub.toJSON())))
        throw new Error("subscribe");
      setState("on");
      setNote("Notifications are on for this device.");
    } catch {
      setNote(
        "This device couldn't turn on notifications. Try again, or use Telegram.",
      );
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = await reg?.pushManager.getSubscription();
      if (sub) {
        await post("/api/push/unsubscribe", { endpoint: sub.endpoint });
        await sub.unsubscribe();
      }
      setState("off");
      setNote("Notifications are off for this device.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "checking")
    return <p className="m-0 text-sm text-mute">Checking this device…</p>;
  if (state === "install") {
    return (
      <div
        className="flex flex-col gap-2 text-sm text-ink-2"
        aria-label="Install guide"
      >
        <p className="m-0 font-medium text-ink">
          On iPhone, add the portal to your Home Screen first.
        </p>
        <ol className="m-0 flex flex-col gap-1 pl-5">
          <li>In Safari, tap the Share button.</li>
          <li>Choose Add to Home Screen, then Add.</li>
          <li>
            Open Trading desk from your Home Screen and come back here to turn
            on notifications.
          </li>
        </ol>
      </div>
    );
  }
  if (state === "unsupported") {
    return (
      <p className="m-0 text-sm text-ink-2">
        This browser can&apos;t receive push notifications. Use Telegram or
        email instead.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {state === "blocked" && (
        <p
          role="status"
          className="m-0 border border-warn-border bg-warn-bg px-3 py-2.5 text-[13px] text-warn-ink"
        >
          Notifications are blocked in this browser. Open the browser&apos;s
          site settings for this portal, allow notifications, then reload this
          page.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {state === "on" ? (
          <Button
            kind="secondary"
            type="button"
            onClick={turnOff}
            disabled={busy}
          >
            Turn off on this device
          </Button>
        ) : (
          <Button
            type="button"
            onClick={turnOn}
            disabled={busy || state === "blocked"}
            className="h-11 text-sm"
          >
            Turn on notifications
          </Button>
        )}
        <span className="text-[13px] text-mute">
          {state === "on" ? "On for this device" : "Off for this device"}
        </span>
      </div>
      {note && (
        <p role="status" className="m-0 text-[13px] text-ink-2">
          {note}
        </p>
      )}
    </div>
  );
}
