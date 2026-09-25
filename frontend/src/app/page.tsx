// Home page placeholder for Milestone 0. It only proves the Next.js + Tailwind
// toolchain renders. Real screens (clients, job board, quote builder) arrive
// in Milestone 5.
//
// In the App Router, `src/app/page.tsx` is the "/" route, and it's a React
// Server Component by default: rendered on the server, with no JS shipped for it.
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
      <h1 className="text-4xl font-semibold tracking-tight">TradeQuote</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Quotes and job tracking for trade contractors.
      </p>
    </main>
  );
}
