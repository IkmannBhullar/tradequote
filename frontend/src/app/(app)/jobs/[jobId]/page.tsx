import Link from "next/link";

import { SubmitButton } from "@/components/SubmitButton";
import { Card, StatusBadge } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { formatCents } from "@/lib/money";
import { createQuote, updateJob } from "../actions";
import { JobForm } from "./JobForm";
import { recordPayment, voidPayment } from "./payment-actions";
import { PaymentsPanel } from "./PaymentsPanel";

export default async function JobPage(props: PageProps<"/jobs/[jobId]">) {
  const { jobId } = await props.params;
  const client = await api();
  const params = { params: { path: { job_id: jobId } } };
  const [job, quotes, payments] = await Promise.all([
    client.GET("/jobs/{job_id}", params).then(unwrap),
    client.GET("/jobs/{job_id}/quotes", params).then(unwrap),
    client.GET("/jobs/{job_id}/payments", params).then(unwrap),
  ]);

  const latest = quotes.at(-1);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/jobs" className="text-sm text-zinc-500 hover:underline">← Jobs</Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{job.title}</h1>
          <StatusBadge status={job.status} />
        </div>
        <p className="text-zinc-500">
          for <Link href={`/clients/${job.client_id}`} className="underline">{job.client_name}</Link>
        </p>
      </div>

      <Card
        title="Quote"
        actions={
          latest ? (
            <Link href={`/quotes/${latest.id}`} className="text-sm underline">Open latest (v{latest.version})</Link>
          ) : (
            <form action={createQuote.bind(null, jobId)}>
              <SubmitButton pendingText="Creating…">Create quote</SubmitButton>
            </form>
          )
        }
      >
        {quotes.length === 0 ? (
          <p className="text-sm text-zinc-500">No quote yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-zinc-500">
              <tr><th className="py-1">Version</th><th>Status</th><th className="text-right">Total</th></tr>
            </thead>
            <tbody>
              {[...quotes].reverse().map((quote) => (
                <tr key={quote.id} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-2"><Link href={`/quotes/${quote.id}`} className="underline">v{quote.version}</Link></td>
                  <td><StatusBadge status={quote.status} /></td>
                  <td className="text-right tabular-nums">{formatCents(quote.total_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* key: remount with fresh data when the job changes status elsewhere. */}
      <PaymentsPanel
        key={`${job.status}-${payments.summary.paid_cents}`}
        jobId={jobId}
        initial={payments}
        actions={{ recordPayment, voidPayment }}
      />

      <Card title="Details">
        <JobForm job={job} action={updateJob.bind(null, jobId)} />
      </Card>
    </div>
  );
}
