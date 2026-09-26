// Money and number formatting for the UI.
//
// The server does ALL pricing math; the browser only formats results and
// converts what the user types into the exact strings/integers the API wants.
// Converting input never uses floating point: in JavaScript 0.07 * 100 is
// 7.000000000000001, so rates and dollar amounts are converted with string
// arithmetic instead.

// Placeholder until KBS confirms their currency.
export const CURRENCY = "USD";

const currencyFormat = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: CURRENCY,
});

/** 48300 -> "$483.00". (Dividing by 100 is safe here: display only.) */
export function formatCents(cents: number): string {
  return currencyFormat.format(cents / 100);
}

/**
 * User-typed dollars -> integer cents, without floats.
 * "65" -> 6500, "65.5" -> 6550, "$1,234.56" -> 123456. Returns null if the
 * text isn't a valid non-negative amount with at most 2 decimal places.
 */
export function dollarsToCents(input: string): number | null {
  const cleaned = input.trim().replace(/^\$/, "").replaceAll(",", "");
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return null;
  const [, whole, fraction = ""] = match;
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

/** Integer cents -> an editable dollar string: 6550 -> "65.50". */
export function centsToDollars(cents: number): string {
  const whole = Math.floor(cents / 100);
  const fraction = String(cents % 100).padStart(2, "0");
  return `${whole}.${fraction}`;
}

/** "3.000" -> "3", "5.250" -> "5.25": drop trailing zeros for display. */
export function formatQuantity(decimal: string): string {
  if (!decimal.includes(".")) return decimal;
  return decimal.replace(/\.?0+$/, "");
}

/**
 * Shift a decimal string's point left or right by `places` (string math).
 * shiftDecimal("0.05", 2) -> "5", shiftDecimal("7.5", -2) -> "0.075".
 */
function shiftDecimal(value: string, places: number): string {
  const [whole, fraction = ""] = value.split(".");
  let digits = whole + fraction;
  let point = whole.length + places;
  if (point <= 0) {
    digits = "0".repeat(1 - point) + digits;
    point = 1;
  }
  if (point > digits.length) digits = digits.padEnd(point, "0");
  const result = `${digits.slice(0, point)}.${digits.slice(point)}`;
  // Normalize: no leading zeros (keep one), no trailing zeros or dot.
  return result.replace(/^0+(?=\d)/, "").replace(/\.?0*$/, "") || "0";
}

/** API tax rate fraction -> percent text: "0.05000" -> "5", "0.04712" -> "4.712". */
export function fractionToPercent(fraction: string): string {
  return shiftDecimal(fraction, 2);
}

/**
 * User-typed percent -> API fraction string, or null if invalid.
 * "5" -> "0.05", "7.5" -> "0.075". At most 3 decimal places in the percent,
 * matching the database's NUMERIC(6,5) fraction.
 */
export function percentToFraction(input: string): string | null {
  const cleaned = input.trim().replace(/%$/, "").trim();
  if (!/^\d+(?:\.\d{1,3})?$/.test(cleaned)) return null;
  return shiftDecimal(cleaned, -2);
}

/** Unit label for a measure type (imperial placeholder until KBS confirms). */
export function measureUnit(measureType: string): string {
  return { area: "sq ft", linear: "ft", count: "count" }[measureType] ?? "";
}
