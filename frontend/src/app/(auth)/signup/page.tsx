import { signup } from "../actions";
import { AuthForm } from "../AuthForm";

export default function SignupPage() {
  return <AuthForm mode="signup" action={signup} />;
}
