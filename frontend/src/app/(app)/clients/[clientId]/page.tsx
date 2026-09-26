import Link from "next/link";

import { Card, StatusBadge } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { createJob, deleteClient, updateClient } from "../actions";
import { ClientForm, DeleteClientButton, NewJobForm } from "../ClientForms";

export default async function ClientPage(props: PageProps<"/clients/[clientId]">) {
  const { clientId } = await props.params;
  const client = await api();
  // Two independent requests, run in parallel.
  const [clientData, jobs] = await Promise.all([
    client.GET("/clients/{client_id}", { params: { path: { client_id: clientId } } }).then(unwrap),
    client.GET("/jobs", { params: { query: { client_id: clientId, limit: 200 } } }).then(unwrap),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/clients" className="text-sm text-zinc-500 hover:underline">← Clients</Link>
          <h1 className="text-2xl font-semibold">{clientData.name}</h1>
        </div>
        {/* .bind pre-fills the client id; the action still re-checks access in FastAPI. */}
        <DeleteClientButton action={deleteClient.bind(null, clientId)} />
      </div>
      <Card title="Jobs">
        <NewJobForm action={createJob.bind(null, clientId)} />
        <ul className="mt-4 divide-y divide-zinc-200 dark:divide-zinc-800">
          {jobs.items.map((job) => (
            <li key={job.id} className="flex items-center justify-between gap-2 py-2">
              <Link href={`/jobs/${job.id}`} className="hover:underline">{job.title}</Link>
              <StatusBadge status={job.status} />
            </li>
          ))}
          {jobs.items.length === 0 ? <li className="py-2 text-sm text-zinc-500">No jobs yet.</li> : null}
        </ul>
      </Card>
      <Card title="Details">
        <ClientForm action={updateClient.bind(null, clientId)} client={clientData} submitLabel="Save" />
      </Card>
    </div>
  );
}
