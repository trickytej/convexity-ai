import { redirect } from "next/navigation";

// The funda-style design preview is now the live Insights experience.
export default function PreviewPage() {
  redirect("/insights");
}
