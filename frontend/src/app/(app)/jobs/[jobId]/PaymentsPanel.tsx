"use client";

// Payments for one job: what's owed, what's been paid, and the history.
// The server computes every number; this component only displays them and
// converts what the user types (dollars -> integer cents, without floats).

import { type FormEvent, useState, useTransition } from "react";

import { Button, Card, ErrorBanner, Input } from "@/components/ui";
import type { ActionResult } from "@/lib/api/errors";
import type { JobPayments, Payment } from "@/lib/api/types";
import { centsToDollars, dollarsToCents, formatCents } from "@/lib/money";
import type { PaymentInput } from "./payment-actions";

type Result = Promise<ActionResult<JobPayments>>;

export interface PaymentActions {
  recordPayment: (jobId: string, input: PaymentInput) => Result;
  voidPayment: (jobId: string, paymentId: string, reason: string) => Result;
}

export function PaymentsPanel({
  jobId,
  initial,
  actions,
}: {
  jobId: string;
  initial: JobPayments;
  actions: PaymentActions;
}) {
  const [data, setData] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const { summary } = data;

  function run(action: () => Result, onSuccess?: () => void) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (!result.ok) return setError(result.error);
      setData(result.data);
      onSuccess?.();
    });
  }

  if (summary.amount_due_cents == null) {
    return (
      <Card title="Payments">
        <p className="text-sm text-zinc-500">Payments can be recorded once the client approves a quote.</p>
      </Card>
    );
  }

  const balance = summary.balance_cents ?? 0;
  return (
    <Card title="Payments">
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Quote total" value={formatCents(summary.amount_due_cents)} />
        <Stat label="Paid" value={formatCents(summary.paid_cents)} />
        <Stat label="Balance" value={formatCents(balance)} testId="balance" strong />
        {summary.deposit_required_cents ? (
          <Stat
            label="Deposit"
            value={summary.deposit_outstanding_cents ? `${formatCents(summary.deposit_outstanding_cents)} due` : "Received"}
          />
        ) : null}
      </dl>

      <div className="mt-4"><ErrorBanner message={error} /></div>

      {data.payments.length > 0 ? (
        <table className="mt-4 w-full text-sm">
          <thead className="text-left text-zinc-500">
            <tr>
              <th className="py-1 font-medium">Date</th>
              <th className="font-medium">Kind</th>
              <th className="font-medium">Method</th>
              <th className="text-right font-medium">Amount</th>
              <th className="sr-only">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.payments.map((payment) => (
              <PaymentRow key={payment.id} payment={payment} disabled={pending} onVoid={(reason) => run(() => actions.voidPayment(jobId, payment.id, reason))} />
            ))}
          </tbody>
        </table>
      ) : null}

      {balance > 0 ? (
        <RecordPaymentForm
          // The business's "today" from the API, not this device's clock
          // (which may be in another timezone).
          today={data.today}
          balance={balance}
          depositOutstanding={summary.deposit_outstanding_cents ?? 0}
          disabled={pending}
          onRecord={(input, reset) => run(() => actions.recordPayment(jobId, input), reset)}
        />
      ) : (
        <p className="mt-4 text-sm font-medium text-emerald-700 dark:text-emerald-400">Paid in full.</p>
      )}
    </Card>
  );
}

function Stat({ label, value, testId, strong }: { label: string; value: string; testId?: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-zinc-500">{label}</dt>
      <dd data-testid={testId} className={`tabular-nums ${strong ? "text-lg font-semibold" : ""}`}>{value}</dd>
    </div>
  );
}

function PaymentRow({ payment, disabled, onVoid }: { payment: Payment; disabled: boolean; onVoid: (reason: string) => void }) {
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState("");
  const voided = payment.voided_at != null;
  return (
    <>
      <tr className={`border-t border-zinc-200 dark:border-zinc-800 ${voided ? "text-zinc-400 line-through" : ""}`}>
        <td className="py-2">{payment.received_on}</td>
        <td className="capitalize">{payment.kind}</td>
        <td>{payment.method ?? "—"}</td>
        <td className="text-right tabular-nums">{formatCents(payment.amount_cents)}</td>
        <td className="text-right">
          {voided ? (
            <span className="text-xs no-underline" title={payment.void_reason ?? ""}>voided</span>
          ) : (
            <Button variant="ghost" className="px-2 text-xs" disabled={disabled} onClick={() => setVoiding(!voiding)}>
              {voiding ? "Cancel" : "Void"}
            </Button>
          )}
        </td>
      </tr>
      {voided && payment.void_reason ? (
        <tr><td colSpan={5} className="pb-2 text-xs text-zinc-500">Voided: {payment.void_reason}</td></tr>
      ) : null}
      {voiding && !voided ? (
        <tr>
          <td colSpan={5} className="pb-3">
            <form
              className="flex flex-wrap items-end gap-2 rounded-md bg-zinc-50 p-2 dark:bg-zinc-800/50"
              onSubmit={(event) => {
                event.preventDefault();
                onVoid(reason.trim());
              }}
            >
              <label className="flex flex-1 flex-col gap-1 text-xs">
                Reason for voiding
                <Input value={reason} onChange={(event) => setReason(event.target.value)} required minLength={3} placeholder="e.g. Cheque bounced" />
              </label>
              <Button type="submit" variant="danger" disabled={disabled || reason.trim().length < 3}>Void payment</Button>
            </form>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function RecordPaymentForm({
  today,
  balance,
  depositOutstanding,
  disabled,
  onRecord,
}: {
  today: string;
  balance: number;
  depositOutstanding: number;
  disabled: boolean;
  onRecord: (input: PaymentInput, reset: () => void) => void;
}) {
  // Suggest the most likely next payment: the deposit if still owed, else the balance.
  const suggestedKind = depositOutstanding > 0 ? "deposit" : "final";
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"deposit" | "final">(suggestedKind);
  const [method, setMethod] = useState("");
  const [receivedOn, setReceivedOn] = useState(today);
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const cents = dollarsToCents(amount);
    if (cents === null || cents === 0) return setError("Enter an amount like 100 or 100.50");
    setError(null);
    onRecord(
      { amount_cents: cents, kind, method: method.trim() || null, received_on: receivedOn },
      () => {
        setAmount("");
        setKind("final");
      },
    );
  }

  return (
    <form onSubmit={submit} className="mt-4 grid gap-2 border-t border-zinc-200 pt-4 sm:grid-cols-[1fr_0.8fr_1fr_1fr_auto] sm:items-end dark:border-zinc-800">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Amount ($)</span>
        <Input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder={centsToDollars(balance)} required />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Kind</span>
        <select value={kind} onChange={(event) => setKind(event.target.value as "deposit" | "final")} className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="deposit">Deposit</option>
          <option value="final">Final</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Method</span>
        <Input list="payment-methods" value={method} onChange={(event) => setMethod(event.target.value)} placeholder="e-transfer" />
        <datalist id="payment-methods">
          <option value="e-transfer" />
          <option value="cheque" />
          <option value="cash" />
          <option value="card" />
        </datalist>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Date received</span>
        <Input type="date" value={receivedOn} max={today} onChange={(event) => setReceivedOn(event.target.value)} required />
      </label>
      <Button type="submit" disabled={disabled}>Record payment</Button>
      {error ? <p className="text-sm text-red-600 sm:col-span-5">{error}</p> : null}
    </form>
  );
}
