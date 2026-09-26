import { redirect } from "next/navigation";

// The job board is home.
export default function Home() {
  redirect("/jobs");
}
