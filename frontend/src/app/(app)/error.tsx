"use client";

import { Button, ErrorBanner } from "@/components/ui";

// Shown when a page or action in the signed-in app throws unexpectedly.
export default function AppError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3">
      <ErrorBanner message={error.message || "Something went wrong."} />
      <Button variant="secondary" onClick={reset}>Try again</Button>
    </div>
  );
}
