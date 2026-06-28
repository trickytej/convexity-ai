import { redirect } from "next/navigation";

// The site lands on the Home dashboard. The podcast library lives at /podcasts.
export default function RootPage() {
  redirect("/insights");
}
