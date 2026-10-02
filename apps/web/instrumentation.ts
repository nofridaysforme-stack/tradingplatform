// Runs once when the server starts. The web service watches the scanner's heartbeat, because a
// stopped scanner cannot report itself (spec 11, lib/watchdog.ts).
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { startWatchdog } = await import("@/lib/watchdog-runner");
    startWatchdog();
  }
}
