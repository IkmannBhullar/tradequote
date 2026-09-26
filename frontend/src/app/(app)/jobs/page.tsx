import Link from "next/link";

import { SubmitButton } from "@/components/SubmitButton";
import { StatusBadge, statusLabel } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import type { JobStatus } from "@/lib/api/types";
import { moveJob } from "./actions";

// Pipeline order, left to right.
const COLUMNS: JobStatus[] = ["quoted", "approved", "scheduled", "in_progress", "completed", "paid"];
const PER_COLUMN = 50;

export default async function JobBoardPage() {
  const client = await api();
  // One request per column, all in parallel.
  const columns = await Promise.all(
    COLUMNS.map((status) =>
      client.GET("/jobs", { params: { query: { status, limit: PER_COLUMN } } }).then(unwrap),
    ),
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Jobs</h1>
        <Link href="/clients" className="text-sm underline">New job → pick a client</Link>
      </div>
      {/* Scrolls sideways on small screens instead of squashing columns. */}
      <div className="grid auto-cols-[minmax(15rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-2">
        {COLUMNS.map((status, index) => {
          const page = columns[index];
          return (
            <section key={status} aria-label={statusLabel(status)} className="flex flex-col gap-2 rounded-lg bg-zinc-100 p-2 dark:bg-zinc-900">
              <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
                <StatusBadge status={status} />
                <span className="text-zinc-500">{page.total}</span>
              </h2>
              {page.items.map((job) => (
                <article key={job.id} className="rounded-md border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
                  <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">{job.title}</Link>
                  <p className="text-zinc-500">{job.client_name}</p>
                  {job.allowed_transitions && job.allowed_transitions.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {job.allowed_transitions.map((target) => (
                        <form key={target} action={moveJob.bind(null, job.id, target)}>
                          <SubmitButton variant="ghost" className="px-2 py-0.5 text-xs" pendingText="Moving…">
                            {COLUMNS.indexOf(target) > COLUMNS.indexOf(status) ? "→" : "←"} {statusLabel(target)}
                          </SubmitButton>
                        </form>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
              {page.total > page.items.length ? (
                <p className="px-1 text-xs text-zinc-500">+{page.total - page.items.length} more</p>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}
