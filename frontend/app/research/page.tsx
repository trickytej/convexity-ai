import { auth } from "@/auth";
import ResearchUploader from "@/components/ResearchUploader";
import SignInCard from "@/components/SignInCard";

export const metadata = { title: "Your research — ConvexityAI" };

// Private research belongs to a signed-in user; demo visitors get an invitation.
export default async function ResearchPage() {
  if ((await auth())?.user?.id) return <ResearchUploader />;
  return (
    <SignInCard
      title="Bring your own research"
      text="Paste notes, link articles or upload PDFs. They stay private to you and are weighed against your What Matters questions alongside everything else. Sign in free to start."
      callbackUrl="/research"
    />
  );
}
