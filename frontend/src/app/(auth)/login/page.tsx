import { login } from "../actions";
import { AuthForm } from "../AuthForm";

export default async function LoginPage(props: PageProps<"/login">) {
  const searchParams = await props.searchParams;
  const next = typeof searchParams.next === "string" ? searchParams.next : undefined;
  const expired = searchParams.expired === "1";
  return (
    <AuthForm
      mode="login"
      action={login}
      next={next}
      notice={expired ? "Your session expired. Please log in again." : undefined}
    />
  );
}
