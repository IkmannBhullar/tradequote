"use client";

// The quote builder. Holds the current quote in state; every edit calls a
// Server Action, which returns the backend's freshly recalculated quote, and
// that replaces the state. The browser never computes a price itself: the
// estimating engine on the server is the single source of truth.

import { useRouter } from "next/navigation";
import { type FormEvent, useState, useTransition } from "react";

import { Button, Card, ErrorBanner, Input, StatusBadge } from "@/components/ui";
import type { ActionResult } from "@/lib/api/errors";
import type { Area, LineItem, Quote, Template } from "@/lib/api/types";
import {
  centsToDollars,
  dollarsToCents,
  formatCents,
  formatQuantity,
  fractionToPercent,
  measureUnit,
} from "@/lib/money";
import type { AreaChanges, AreaInput, OverrideInput } from "./actions";

type Result = Promise<ActionResult<Quote>>;

/** Passed in as props (not imported) so tests can supply fakes. */
export interface QuoteActions {
  addArea: (quoteId: string, input: AreaInput) => Result;
  updateArea: (quoteId: string, areaId: string, changes: AreaChanges) => Result;
  deleteArea: (quoteId: string, areaId: string) => Result;
  setOverride: (quoteId: string, lineId: string, input: OverrideInput) => Result;
  clearOverride: (quoteId: string, lineId: string) => Result;
  updateDeposit: (quoteId: string, cents: number) => Result;
  refreshRates: (quoteId: string) => Result;
  createRevision: (quoteId: string) => Result;
}

export function QuoteBuilder({
  initialQuote,
  templates,
  actions,
}: {
  initialQuote: Quote;
  templates: Template[];
  actions: QuoteActions;
}) {
  const [quote, setQuote] = useState(initialQuote);
  const [error, setError] = useState<string | null>(null);
  // A transition keeps the UI responsive and gives us `pending` while the
  // server recalculates.
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  const editable = quote.status === "draft";

  /** Run an action; on success show the new quote, on failure the error. */
  function run(action: () => Result, onSuccess?: (updated: Quote) => void) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (result.ok) {
        setQuote(result.data);
        onSuccess?.(result.data);
      } else {
        const details = result.fieldErrors ? Object.values(result.fieldErrors).join(" ") : "";
        setError(details ? `${result.error} ${details}` : result.error);
      }
    });
  }

  return (
    <div className="flex flex-col gap-4" aria-busy={pending}>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Quote v{quote.version}</h1>
        <StatusBadge status={quote.status} />
        {pending ? <span className="text-sm text-zinc-500">Updating…</span> : null}
        <div className="ml-auto flex gap-2">
          {editable ? (
            <Button variant="secondary" disabled={pending} onClick={() => run(() => actions.refreshRates(quote.id))}>
              Refresh rates
            </Button>
          ) : (
            <Button
              disabled={pending}
              onClick={() =>
                run(
                  () => actions.createRevision(quote.id),
                  (revision) => router.push(`/quotes/${revision.id}`),
                )
              }
            >
              Create revision
            </Button>
          )}
        </div>
      </div>

      {!editable ? (
        <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-800">
          This quote is {quote.status} and can no longer be edited. Create a revision to make changes.
        </p>
      ) : null}
      <ErrorBanner message={error} />

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="flex flex-col gap-4">
          <Card title="Areas">
            <AreasTable quote={quote} editable={editable} disabled={pending} run={run} actions={actions} />
            {editable ? (
              <AddAreaForm quoteId={quote.id} templates={templates} disabled={pending} run={run} actions={actions} />
            ) : null}
          </Card>
          <Card title="Line items">
            <LineItemsTable quote={quote} editable={editable} disabled={pending} run={run} actions={actions} />
          </Card>
        </div>
        <TotalsCard quote={quote} editable={editable} disabled={pending} run={run} actions={actions} />
      </div>
    </div>
  );
}

type Run = (action: () => Result, onSuccess?: (updated: Quote) => void) => void;
type SectionProps = { quote: Quote; editable: boolean; disabled: boolean; run: Run; actions: QuoteActions };

// --- Areas ------------------------------------------------------------------

function AreasTable({ quote, editable, disabled, run, actions }: SectionProps) {
  if (quote.areas.length === 0) return <p className="text-sm text-zinc-500">No areas yet. Add what you measured below.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-zinc-500">
        <tr>
          <th className="py-1 font-medium">Area</th>
          <th className="font-medium">Quantity</th>
          <th className="font-medium">Coats</th>
          <th className="sr-only">Actions</th>
        </tr>
      </thead>
      <tbody>
        {quote.areas.map((area) => (
          <AreaRow key={area.id} quoteId={quote.id} area={area} editable={editable} disabled={disabled} run={run} actions={actions} />
        ))}
      </tbody>
    </table>
  );
}

function AreaRow({
  quoteId,
  area,
  editable,
  disabled,
  run,
  actions,
}: { quoteId: string; area: Area } & Omit<SectionProps, "quote">) {
  // Save a field when the user leaves it, only if it actually changed.
  function saveOnBlur(field: keyof AreaChanges, raw: string, current: string) {
    const value = raw.trim();
    if (value === "" || value === current) return;
    const changes: AreaChanges = field === "coats" ? { coats: Number(value) } : { [field]: value };
    run(() => actions.updateArea(quoteId, area.id, changes));
  }

  return (
    <tr className="border-t border-zinc-200 dark:border-zinc-800">
      <td className="py-2 pr-2">
        <Input
          aria-label={`Name of ${area.name}`}
          defaultValue={area.name}
          disabled={!editable || disabled}
          onBlur={(event) => saveOnBlur("name", event.target.value, area.name)}
        />
        <span className="text-xs text-zinc-500">{area.material_name}</span>
      </td>
      <td className="pr-2">
        <div className="flex items-center gap-1">
          <Input
            aria-label={`Quantity of ${area.name}`}
            inputMode="decimal"
            className="w-24"
            defaultValue={formatQuantity(area.quantity)}
            disabled={!editable || disabled}
            onBlur={(event) => saveOnBlur("quantity", event.target.value, formatQuantity(area.quantity))}
          />
          <span className="whitespace-nowrap text-xs text-zinc-500">{measureUnit(area.measure_type)}</span>
        </div>
      </td>
      <td className="pr-2">
        <Input
          aria-label={`Coats for ${area.name}`}
          inputMode="numeric"
          className="w-16"
          defaultValue={String(area.coats)}
          disabled={!editable || disabled}
          onBlur={(event) => saveOnBlur("coats", event.target.value, String(area.coats))}
        />
      </td>
      <td className="text-right">
        {editable ? (
          <Button variant="ghost" disabled={disabled} onClick={() => run(() => actions.deleteArea(quoteId, area.id))} aria-label={`Remove ${area.name}`}>
            Remove
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

function AddAreaForm({
  quoteId,
  templates,
  disabled,
  run,
  actions,
}: { quoteId: string; templates: Template[]; disabled: boolean; run: Run; actions: QuoteActions }) {
  const [itemId, setItemId] = useState("");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [coats, setCoats] = useState("");
  const items = templates.flatMap((template) => template.items);
  const selected = items.find((item) => item.id === itemId);

  function submit(event: FormEvent) {
    event.preventDefault();
    run(
      () =>
        actions.addArea(quoteId, {
          template_item_id: itemId,
          name: name.trim() || selected?.name || "",
          quantity: quantity.trim(),
          coats: coats.trim() === "" ? null : Number(coats),
        }),
      () => {
        // Clear the form for the next area, keeping the item selected.
        setName("");
        setQuantity("");
        setCoats("");
      },
    );
  }

  return (
    <form onSubmit={submit} className="mt-4 grid gap-2 border-t border-zinc-200 pt-4 sm:grid-cols-[1.2fr_1fr_0.7fr_0.5fr_auto] sm:items-end dark:border-zinc-800">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Item</span>
        <select
          required
          value={itemId}
          onChange={(event) => setItemId(event.target.value)}
          className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="" disabled>Choose…</option>
          {templates.map((template) => (
            <optgroup key={template.id} label={template.name}>
              {template.items.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Area name</span>
        <Input value={name} onChange={(event) => setName(event.target.value)} placeholder={selected?.name ?? "Living room walls"} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Quantity{selected ? ` (${measureUnit(selected.measure_type)})` : ""}</span>
        <Input required inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Coats</span>
        <Input inputMode="numeric" value={coats} onChange={(event) => setCoats(event.target.value)} placeholder={selected ? String(selected.default_coats) : ""} />
      </label>
      <Button type="submit" disabled={disabled || !itemId}>Add area</Button>
    </form>
  );
}

// --- Line items and overrides ------------------------------------------------

function LineItemsTable({ quote, editable, disabled, run, actions }: SectionProps) {
  if (quote.line_items.length === 0) return <p className="text-sm text-zinc-500">Line items appear once you add areas.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-zinc-500">
        <tr>
          <th className="py-1 font-medium">Description</th>
          <th className="text-right font-medium">Qty</th>
          <th className="text-right font-medium">Unit price</th>
          <th className="text-right font-medium">Total</th>
          <th className="sr-only">Override</th>
        </tr>
      </thead>
      <tbody>
        {quote.line_items.map((line) => (
          <LineRow key={line.id} quoteId={quote.id} line={line} editable={editable} disabled={disabled} run={run} actions={actions} />
        ))}
      </tbody>
    </table>
  );
}

function LineRow({
  quoteId,
  line,
  editable,
  disabled,
  run,
  actions,
}: { quoteId: string; line: LineItem } & Omit<SectionProps, "quote">) {
  const [editing, setEditing] = useState(false);
  const [quantity, setQuantity] = useState(line.override_quantity ? formatQuantity(line.override_quantity) : "");
  const [price, setPrice] = useState(line.override_unit_price_cents != null ? centsToDollars(line.override_unit_price_cents) : "");
  const [error, setError] = useState<string | null>(null);

  function saveOverride(event: FormEvent) {
    event.preventDefault();
    const cents = price.trim() === "" ? null : dollarsToCents(price);
    if (cents === null && price.trim() !== "") return setError("Enter a price like 45 or 45.50");
    if (quantity.trim() === "" && cents === null) return setError("Set a quantity, a price, or both");
    setError(null);
    run(
      () => actions.setOverride(quoteId, line.id, { quantity: quantity.trim() || null, unit_price_cents: cents }),
      () => setEditing(false),
    );
  }

  return (
    <>
      <tr className="border-t border-zinc-200 dark:border-zinc-800">
        <td className="py-2">
          {line.description}
          {line.is_override ? <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">edited</span> : null}
        </td>
        <td className="text-right tabular-nums">{formatQuantity(line.quantity)} {line.unit}</td>
        <td className="text-right tabular-nums">{formatCents(line.unit_price_cents)}</td>
        <td className="text-right font-medium tabular-nums">{formatCents(line.total_cents)}</td>
        <td className="text-right">
          {editable ? (
            <div className="flex justify-end gap-1">
              <Button variant="ghost" className="px-2 text-xs" disabled={disabled} onClick={() => setEditing(!editing)}>
                {editing ? "Cancel" : "Override"}
              </Button>
              {line.is_override ? (
                <Button variant="ghost" className="px-2 text-xs" disabled={disabled} onClick={() => run(() => actions.clearOverride(quoteId, line.id))}>
                  Reset
                </Button>
              ) : null}
            </div>
          ) : null}
        </td>
      </tr>
      {editing ? (
        <tr>
          <td colSpan={5} className="pb-3">
            <form onSubmit={saveOverride} className="flex flex-wrap items-end gap-2 rounded-md bg-zinc-50 p-2 dark:bg-zinc-800/50">
              <label className="flex flex-col gap-1 text-xs">
                Quantity ({line.unit})
                <Input className="w-28" inputMode="decimal" value={quantity} placeholder={formatQuantity(line.quantity)} onChange={(event) => setQuantity(event.target.value)} />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                Unit price ($)
                <Input className="w-28" inputMode="decimal" value={price} placeholder={centsToDollars(line.unit_price_cents)} onChange={(event) => setPrice(event.target.value)} />
              </label>
              <Button type="submit" disabled={disabled}>Save override</Button>
              <span className="text-xs text-zinc-500">Leave a field empty to keep calculating it.</span>
              {error ? <p className="w-full text-xs text-red-600">{error}</p> : null}
            </form>
          </td>
        </tr>
      ) : null}
    </>
  );
}

// --- Totals and deposit --------------------------------------------------------

function TotalsCard({ quote, editable, disabled, run, actions }: SectionProps) {
  const [deposit, setDeposit] = useState(centsToDollars(quote.deposit_required_cents));
  const [error, setError] = useState<string | null>(null);

  function saveDeposit(event: FormEvent) {
    event.preventDefault();
    const cents = dollarsToCents(deposit);
    if (cents === null) return setError("Enter an amount like 100 or 100.50");
    setError(null);
    run(() => actions.updateDeposit(quote.id, cents), (updated) => setDeposit(centsToDollars(updated.deposit_required_cents)));
  }

  return (
    <Card title="Totals">
      <dl className="grid grid-cols-[1fr_auto] gap-y-1 text-sm">
        <dt className="text-zinc-500">Subtotal</dt>
        <dd className="text-right tabular-nums" data-testid="subtotal">{formatCents(quote.subtotal_cents)}</dd>
        <dt className="text-zinc-500">Tax ({fractionToPercent(quote.tax_rate)}%)</dt>
        <dd className="text-right tabular-nums">{formatCents(quote.tax_cents)}</dd>
        <dt className="border-t border-zinc-200 pt-2 font-semibold dark:border-zinc-800">Total</dt>
        <dd className="border-t border-zinc-200 pt-2 text-right text-lg font-semibold tabular-nums dark:border-zinc-800" data-testid="total">
          {formatCents(quote.total_cents)}
        </dd>
      </dl>
      <p className="mt-2 text-xs text-zinc-500">Labor at {formatCents(quote.labor_rate_cents)}/hour</p>
      <form onSubmit={saveDeposit} className="mt-4 flex flex-col gap-1 border-t border-zinc-200 pt-4 text-sm dark:border-zinc-800">
        <label htmlFor="deposit" className="font-medium">Deposit required ($)</label>
        <div className="flex gap-2">
          <Input id="deposit" inputMode="decimal" value={deposit} disabled={!editable || disabled} onChange={(event) => setDeposit(event.target.value)} />
          {editable ? <Button type="submit" variant="secondary" disabled={disabled}>Save</Button> : null}
        </div>
        {error ? <p className="text-xs text-red-600">{error}</p> : null}
      </form>
    </Card>
  );
}
