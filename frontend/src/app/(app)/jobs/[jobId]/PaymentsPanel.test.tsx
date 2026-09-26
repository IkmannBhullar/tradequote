// Behavior tests for the payments panel, with fake Server Actions.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { JobPayments } from "@/lib/api/types";
import { PaymentsPanel, type PaymentActions } from "./PaymentsPanel";

const OWED: JobPayments = {
  today: "2026-09-25",
  job_status: "completed",
  payments: [],
  summary: {
    amount_due_cents: 48300,
    paid_cents: 0,
    balance_cents: 48300,
    deposit_required_cents: 10000,
    deposit_outstanding_cents: 10000,
  },
};

const DEPOSIT = {
  id: "pay-1",
  amount_cents: 10000,
  kind: "deposit" as const,
  method: "e-transfer",
  received_on: "2026-09-20",
  voided_at: null,
  void_reason: null,
  created_at: "2026-09-20T12:00:00Z",
};

const AFTER_DEPOSIT: JobPayments = {
  ...OWED,
  payments: [DEPOSIT],
  summary: { ...OWED.summary, paid_cents: 10000, balance_cents: 38300, deposit_outstanding_cents: 0 },
};

function fakeActions(): PaymentActions {
  return {
    recordPayment: vi.fn(() => Promise.resolve({ ok: true as const, data: AFTER_DEPOSIT })),
    voidPayment: vi.fn(() =>
      Promise.resolve({
        ok: true as const,
        data: { ...OWED, payments: [{ ...DEPOSIT, voided_at: "2026-09-21T12:00:00Z", void_reason: "Cheque bounced" }] },
      }),
    ),
  };
}

function renderPanel(initial: JobPayments, actions = fakeActions()) {
  render(<PaymentsPanel jobId="job-1" initial={initial} actions={actions} />);
  return { actions, user: userEvent.setup() };
}

describe("PaymentsPanel", () => {
  it("records a payment in exact cents and shows the new balance", async () => {
    const { actions, user } = renderPanel(OWED);
    expect(screen.getByTestId("balance")).toHaveTextContent("$483.00");

    await user.type(screen.getByLabelText("Amount ($)"), "100");
    await user.type(screen.getByLabelText("Method"), "e-transfer");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(actions.recordPayment).toHaveBeenCalledWith("job-1", {
      amount_cents: 10000,
      kind: "deposit", // suggested while the deposit is outstanding
      method: "e-transfer",
      received_on: "2026-09-25",
    });
    expect(await screen.findByText("$383.00")).toBeInTheDocument();
  });

  it("validates the amount before calling the server", async () => {
    const { actions, user } = renderPanel(OWED);
    await user.type(screen.getByLabelText("Amount ($)"), "12.345");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(screen.getByText(/enter an amount/i)).toBeInTheDocument();
    expect(actions.recordPayment).not.toHaveBeenCalled();
  });

  it("shows the server's error, e.g. an overpayment", async () => {
    const actions = fakeActions();
    actions.recordPayment = vi.fn(() =>
      Promise.resolve({ ok: false as const, error: "That's more than the remaining balance of $483.00" }),
    );
    const { user } = renderPanel(OWED, actions);

    await user.type(screen.getByLabelText("Amount ($)"), "9999");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("more than the remaining balance");
  });

  it("voids a payment only with a reason", async () => {
    const { actions, user } = renderPanel(AFTER_DEPOSIT);
    await user.click(screen.getByRole("button", { name: "Void" }));
    const submit = screen.getByRole("button", { name: "Void payment" });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText("Reason for voiding"), "Cheque bounced");
    await user.click(submit);

    expect(actions.voidPayment).toHaveBeenCalledWith("job-1", "pay-1", "Cheque bounced");
    expect(await screen.findByText("Voided: Cheque bounced")).toBeInTheDocument();
  });

  it("explains that payments wait for an approved quote", () => {
    renderPanel({
      today: "2026-09-25",
      job_status: "quoted",
      payments: [],
      summary: { amount_due_cents: null, paid_cents: 0, balance_cents: null, deposit_required_cents: null, deposit_outstanding_cents: null },
    });
    expect(screen.getByText(/once the client approves a quote/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
  });

  it("hides the form once paid in full", () => {
    renderPanel({ ...OWED, job_status: "paid", summary: { ...OWED.summary, paid_cents: 48300, balance_cents: 0, deposit_outstanding_cents: 0 } });
    expect(screen.getByText("Paid in full.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
  });
});
