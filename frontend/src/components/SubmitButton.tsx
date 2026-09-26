"use client";

import { useFormStatus } from "react-dom";
import type { ComponentProps } from "react";

import { Button } from "./ui";

/**
 * A submit button that disables itself while its form's Server Action runs,
 * so users get feedback and can't double-submit. useFormStatus reads the
 * status of the <form> this button sits in, so it must be a Client Component
 * rendered inside that form.
 */
export function SubmitButton({ children, pendingText, ...props }: ComponentProps<typeof Button> & { pendingText?: string }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending || props.disabled} aria-disabled={pending} {...props}>
      {pending ? (pendingText ?? "…") : children}
    </Button>
  );
}
