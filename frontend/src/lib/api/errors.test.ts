import { describe, expect, it } from "vitest";

import { parseApiError } from "./errors";

describe("parseApiError", () => {
  it("passes through domain error messages", () => {
    expect(parseApiError({ detail: "Client not found" }, 404)).toEqual({ error: "Client not found" });
  });

  it("maps validation errors to their fields", () => {
    const body = {
      detail: [
        { loc: ["body", "quantity"], msg: "Input should be greater than or equal to 0" },
        { loc: ["body", "name"], msg: "String should have at least 1 character" },
      ],
    };
    expect(parseApiError(body, 422)).toEqual({
      error: "Please fix the highlighted fields.",
      fieldErrors: {
        quantity: "Input should be greater than or equal to 0",
        name: "String should have at least 1 character",
      },
    });
  });

  it("puts body-level errors under 'form' and cleans Pydantic's prefix", () => {
    const body = { detail: [{ loc: ["body"], msg: "Value error, set quantity, unit_price_cents, or both" }] };
    expect(parseApiError(body, 422).fieldErrors).toEqual({ form: "set quantity, unit_price_cents, or both" });
  });

  it("falls back to a generic message", () => {
    expect(parseApiError(null, 500).error).toMatch(/something went wrong/i);
    expect(parseApiError("oops", 400).error).toBe("Request failed.");
  });
});
