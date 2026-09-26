// Shown (with HTTP 404) for links that don't match any quote: mistyped,
// or replaced by a newer link.
export default function QuoteLinkNotFound() {
  return (
    <main className="mx-auto flex max-w-lg flex-1 flex-col justify-center gap-2 p-6 text-center">
      <h1 className="text-xl font-semibold">Quote not found</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        This link isn&apos;t valid. It may have been replaced by a newer one; ask your contractor for the latest link.
      </p>
    </main>
  );
}
