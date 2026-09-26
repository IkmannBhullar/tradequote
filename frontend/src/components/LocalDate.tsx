"use client";

/**
 * A date shown in the VIEWER's timezone, e.g. "Sep 25, 2026".
 *
 * The page is rendered twice: on the server, then in the browser. If they're
 * in different timezones the text can differ ("Sep 25" vs "Sep 26"), which
 * React reports as a hydration mismatch. suppressHydrationWarning tells React
 * that this one difference is expected; the browser's version wins.
 */
export function LocalDate({ value }: { value: string }) {
  const text = new Date(value).toLocaleDateString("en-US", { dateStyle: "medium" });
  return (
    <time dateTime={value} suppressHydrationWarning>
      {text}
    </time>
  );
}
