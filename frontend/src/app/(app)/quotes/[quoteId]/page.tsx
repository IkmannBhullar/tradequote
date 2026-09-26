import Link from "next/link";

import { api, unwrap } from "@/lib/api/client";
import * as quoteActions from "./actions";
import { QuoteBuilder } from "./QuoteBuilder";

export default async function QuotePage(props: PageProps<"/quotes/[quoteId]">) {
  const { quoteId } = await props.params;
  const client = await api();
  const [quote, templates] = await Promise.all([
    client.GET("/quotes/{quote_id}", { params: { path: { quote_id: quoteId } } }).then(unwrap),
    client.GET("/templates").then(unwrap),
  ]);
  const job = unwrap(await client.GET("/jobs/{job_id}", { params: { path: { job_id: quote.job_id } } }));

  return (
    <div className="flex flex-col gap-2">
      <Link href={`/jobs/${job.id}`} className="text-sm text-zinc-500 hover:underline">
        ← {job.title} · {job.client_name}
      </Link>
      {/* key: navigating to another version remounts the builder with fresh state. */}
      <QuoteBuilder
        key={quote.id}
        initialQuote={quote}
        templates={templates}
        actions={{
          addArea: quoteActions.addArea,
          updateArea: quoteActions.updateArea,
          deleteArea: quoteActions.deleteArea,
          setOverride: quoteActions.setOverride,
          clearOverride: quoteActions.clearOverride,
          updateDeposit: quoteActions.updateDeposit,
          refreshRates: quoteActions.refreshRates,
          createRevision: quoteActions.createRevision,
        }}
      />
    </div>
  );
}
