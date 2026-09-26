import Link from "next/link";
import type { ReactNode } from "react";

import { logout } from "@/app/(auth)/actions";
import { api, unwrap } from "@/lib/api/client";

// Shell for every signed-in page. Loading /me doubles as the real session
// check: an expired or invalid token sends the user to login (see unwrap).
export default async function AppLayout({ children }: { children: ReactNode }) {
  const me = unwrap(await (await api()).GET("/me"));

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <nav className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 text-sm">
          <Link href="/jobs" className="text-base font-semibold tracking-tight">
            TradeQuote
          </Link>
          <Link href="/jobs" className="hover:underline">Jobs</Link>
          <Link href="/clients" className="hover:underline">Clients</Link>
          <Link href="/settings" className="hover:underline">Settings</Link>
          <span className="ml-auto text-zinc-500">{me.organization.name}</span>
          <form action={logout}>
            <button type="submit" className="text-zinc-600 hover:underline dark:text-zinc-400">
              Log out
            </button>
          </form>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
