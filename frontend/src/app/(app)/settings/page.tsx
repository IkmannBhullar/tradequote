import { api, unwrap } from "@/lib/api/client";
import { SettingsForm } from "./SettingsForm";

export default async function SettingsPage(props: PageProps<"/settings">) {
  const [{ organization }, searchParams] = await Promise.all([
    (await api()).GET("/me").then(unwrap),
    props.searchParams,
  ]);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Settings</h1>
      {searchParams.welcome ? (
        <p className="max-w-md rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:bg-blue-950 dark:text-blue-200">
          Welcome! Set your labor and tax rates before creating quotes.
        </p>
      ) : null}
      <SettingsForm organization={organization} />
    </div>
  );
}
