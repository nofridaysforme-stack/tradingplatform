import { rmSync } from "node:fs";
import { MAILBOX } from "./env";
import { resetMarket, resetUser, setForex } from "./db";

export default async function globalSetup() {
  rmSync(MAILBOX, { recursive: true, force: true });
  await resetUser();
  await resetMarket();
  await setForex(true);
}
