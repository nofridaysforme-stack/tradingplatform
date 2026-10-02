import { rmSync } from "node:fs";
import { MAILBOX } from "./env";
import { resetUser } from "./db";

export default async function globalSetup() {
  rmSync(MAILBOX, { recursive: true, force: true });
  await resetUser();
}
