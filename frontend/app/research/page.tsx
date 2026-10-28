import { auth } from "@/auth";
import ResearchUploader from "@/components/ResearchUploader";
import SignInCard from "@/components/SignInCard";

export const metadata = { title: "Your research — ConvexityAI" };

// Private research belongs to a signed-in user; demo visitors get an invitation.
export default async function ResearchPage() {
  const user = (await auth())?.user;
  if (user?.isAdmin) return <ResearchUploader />;
  // Reading research calls Claude, so it's admin-only until Pro launches.
  if (user?.id) {
    return (
      <SignInCard
        title="Bring your own research: coming with Pro"
        text="Soon you'll be able to paste notes, link articles or upload PDFs, kept private to you and weighed against your What Matters questions alongside everything else."
        callbackUrl="/pro"
        cta="See what's in Pro"
        href="/pro"
      />
    );
  }
  return (
    <SignInCard
      title="Bring your own research"
      text="Paste notes, link articles or upload PDFs. They stay private to you and are weighed against your What Matters questions alongside everything else. Sign in free to start."
      callbackUrl="/research"
    />
  );
}
