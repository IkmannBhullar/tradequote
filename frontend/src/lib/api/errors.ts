// Turning FastAPI error responses into messages people can read.
//
// FastAPI sends either {"detail": "Client not found"} (our domain errors) or,
// for validation failures, {"detail": [{"loc": ["body", "quantity"], "msg": ...}]}.

export type FieldErrors = Record<string, string>;

/** What a Server Action hands back to the UI: data, or a displayable error. */
export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; fieldErrors?: FieldErrors };

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

function isValidationIssueList(value: unknown): value is ValidationIssue[] {
  return Array.isArray(value) && value.every((item) => typeof item === "object" && item !== null);
}

// Pydantic prefixes some messages ("Value error, deposit can't...").
function cleanMessage(message: string): string {
  return message.replace(/^Value error, /, "");
}

export function parseApiError(body: unknown, status: number): { error: string; fieldErrors?: FieldErrors } {
  const detail = typeof body === "object" && body !== null ? (body as { detail?: unknown }).detail : undefined;

  if (typeof detail === "string") {
    return { error: detail };
  }
  if (isValidationIssueList(detail) && detail.length > 0) {
    const fieldErrors: FieldErrors = {};
    for (const issue of detail) {
      // The last part of loc is the field name ("quantity"); body-level
      // errors (e.g. "set quantity or unit price") have only ["body"].
      const field = issue.loc && issue.loc.length > 1 ? String(issue.loc[issue.loc.length - 1]) : "form";
      fieldErrors[field] ??= cleanMessage(issue.msg ?? "Invalid value");
    }
    return { error: "Please fix the highlighted fields.", fieldErrors };
  }
  return { error: status >= 500 ? "Something went wrong on our side. Please try again." : "Request failed." };
}
