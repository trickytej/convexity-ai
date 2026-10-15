import { redirect } from "next/navigation";

// The old Home moved to the public landing page at /.
export default function InsightsPage() {
  redirect("/");
}
