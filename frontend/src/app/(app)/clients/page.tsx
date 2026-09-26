import Link from "next/link";

import { Card } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { createClient } from "./actions";
import { ClientForm } from "./ClientForms";

const PAGE_SIZE = 25;

export default async function ClientsPage(props: PageProps<"/clients">) {
  const searchParams = await props.searchParams;
  const page = Math.max(1, Number(searchParams.page) || 1);
  const clients = unwrap(
    await (await api()).GET("/clients", {
      params: { query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } },
    }),
  );
  const lastPage = Math.max(1, Math.ceil(clients.total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Clients</h1>
      <Card title="New client">
        <ClientForm action={createClient} submitLabel="Add client" />
      </Card>
      <Card title={`All clients (${clients.total})`}>
        {clients.items.length === 0 ? (
          <p className="text-sm text-zinc-500">No clients yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {clients.items.map((client) => (
              <li key={client.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                <Link href={`/clients/${client.id}`} className="font-medium hover:underline">{client.name}</Link>
                <span className="text-sm text-zinc-500">{[client.email, client.phone].filter(Boolean).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
        {lastPage > 1 ? (
          <div className="mt-3 flex items-center gap-3 text-sm">
            {page > 1 ? <Link className="underline" href={`/clients?page=${page - 1}`}>← Previous</Link> : null}
            <span className="text-zinc-500">Page {page} of {lastPage}</span>
            {page < lastPage ? <Link className="underline" href={`/clients?page=${page + 1}`}>Next →</Link> : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
