/** One CSV cell. Text that a spreadsheet would read as a formula is prefixed with a quote
 *  (CSV injection); numbers are written as numbers. */
export function csvCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe;
}

export function csvLine(values: (string | number | boolean | null | undefined)[]): string {
  return values.map(csvCell).join(",");
}
