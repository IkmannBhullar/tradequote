import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { LocalDate } from "@/components/LocalDate";
import { parseApiError } from "@/lib/api/errors";
import { publicApi, quoteToken } from "@/lib/api/public";
import { formatCents, formatQuantity, fractionToPercent } from "@/lib/money";
import { approveQuote, declineQuote } from "./actions";
import { DecisionForms } from "./DecisionForms";

// A private page behind a secret link: keep it out of search engines, and
// don't leak the link (which is in the URL) to other sites via Referer.
export const metadata: Metadata = {
  title: "Your quote",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex max-w-lg flex-1 flex-col justify-center gap-2 p-6 text-center">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-zinc-600 dark:text-zinc-400">{children}</p>
    </main>
  );
}

export default async function PublicQuotePage(props: PageProps<"/q/[token]">) {
  const { token } = await props.params;
  const { data: quote, error, response } = await (await publicApi()).GET("/public/quote", quoteToken(token));

  if (!quote) {
    if (response.status === 410) return <Notice title="This link has expired">{parseApiError(error, 410).error}</Notice>;
    if (response.status === 429) return <Notice title="Please wait a moment">Too many requests. Try again in a minute.</Notice>;
    notFound(); // renders ./not-found.tsx with a real 404 status
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <header className="flex flex-wrap items-end justify-between gap-2 border-b-4 border-blue-900 pb-3">
        <h1 className="text-2xl font-bold text-blue-900 dark:text-blue-300">{quote.organization_name}</h1>
        <p className="text-sm tracking-widest text-zinc-500">QUOTE · VERSION {quote.version}</p>
      </header>

      <section className="text-sm">
        <p className="text-xs font-semibold uppercase text-zinc-500">Prepared for</p>
        <p className="font-semibold">{quote.client_name}</p>
        <p>{quote.job_title}</p>
        {quote.job_address ? <p>{quote.job_address}</p> : null}
      </section>

      {quote.status === "approved" ? (
        <p role="status" className="rounded-md bg-green-50 px-3 py-2 text-green-900 dark:bg-green-950 dark:text-green-200">
          Approved by <strong>{quote.approved_by_name}</strong>
          {quote.approved_at ? <> on <LocalDate value={quote.approved_at} /></> : null}. Thank you!
        </p>
      ) : null}
      {quote.status === "declined" ? (
        <p role="status" className="rounded-md bg-red-50 px-3 py-2 text-red-900 dark:bg-red-950 dark:text-red-200">
          Declined by <strong>{quote.declined_by_name}</strong>. Your contractor has been notified in their dashboard.
        </p>
      ) : null}
      {!quote.is_latest_version ? (
        <p role="status" className="rounded-md bg-amber-50 px-3 py-2 text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          This quote has been replaced by a newer version. Ask your contractor for the latest link.
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-zinc-500">
            <tr>
              <th className="py-2">Description</th>
              <th className="text-right">Qty</th>
              <th className="pl-2">Unit</th>
              <th className="text-right">Unit price</th>
              <th className="text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {quote.lines.map((line, index) => (
              <tr key={index} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-2">{line.description}</td>
                <td className="text-right tabular-nums">{formatQuantity(line.quantity)}</td>
                <td className="pl-2">{line.unit}</td>
                <td className="text-right tabular-nums">{formatCents(line.unit_price_cents)}</td>
                <td className="text-right tabular-nums">{formatCents(line.total_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="ml-auto grid w-full max-w-xs grid-cols-[1fr_auto] gap-y-1 text-sm">
        <dt className="text-zinc-500">Subtotal</dt>
        <dd className="text-right tabular-nums">{formatCents(quote.subtotal_cents)}</dd>
        <dt className="text-zinc-500">Tax ({fractionToPercent(quote.tax_rate)}%)</dt>
        <dd className="text-right tabular-nums">{formatCents(quote.tax_cents)}</dd>
        <dt className="border-t border-zinc-300 pt-2 font-semibold dark:border-zinc-700">Total</dt>
        <dd className="border-t border-zinc-300 pt-2 text-right text-lg font-semibold tabular-nums dark:border-zinc-700" data-testid="public-total">
          {formatCents(quote.total_cents)}
        </dd>
        {quote.deposit_required_cents > 0 ? (
          <>
            <dt className="text-zinc-500">Deposit to schedule</dt>
            <dd className="text-right tabular-nums">{formatCents(quote.deposit_required_cents)}</dd>
          </>
        ) : null}
      </dl>

      <p className="text-sm">
        <a href={`/q/${token}/pdf`} target="_blank" rel="noopener" className="underline">Download PDF</a>
        <span className="text-zinc-500"> · Link valid until <LocalDate value={quote.link_expires_at} /></span>
      </p>

      {quote.can_decide ? (
        // .bind pre-fills the token argument of each Server Action.
        <DecisionForms approve={approveQuote.bind(null, token)} decline={declineQuote.bind(null, token)} />
      ) : null}
    </main>
  );
}
