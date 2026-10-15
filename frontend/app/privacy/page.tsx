import LegalPage from "@/components/LegalPage";

export const metadata = { title: "Privacy — ConvexityAI" };

export default function PrivacyPage() {
  return (
    <LegalPage
      eyebrow="Privacy"
      title="Privacy policy"
      updated="October 15, 2026"
      sections={[
        {
          heading: "What we collect",
          body: [
            "When you sign in with Google we receive your name, email address and profile picture. We use them only to identify your account.",
            "We store what you create in ConvexityAI: the securities you follow, your What Matters questions, your keep/drop decisions, your model numbers, research you upload, and API tokens you create (stored only as a one-way hash).",
          ],
        },
        {
          heading: "How we use it",
          body: [
            "Your data is used to run the service for you — matching research against your questions, building your brief and model, and keeping you signed in. We do not sell your data or use it for advertising.",
            "Research you upload is private to your account: it is matched only against your own questions and is not shown to other users.",
          ],
        },
        {
          heading: "Service providers",
          body: [
            "ConvexityAI runs on third-party infrastructure: Vercel (website), Render (API), Turso (database) and Google (sign-in). Research text and questions are processed by Anthropic's Claude models to extract insights and match them to your questions; audio is transcribed by AssemblyAI.",
          ],
        },
        {
          heading: "Your choices",
          body: [
            "You can delete uploaded research and revoke API tokens at any time in the app. To delete your account and its data, contact us at the address below.",
          ],
        },
        {
          heading: "Contact",
          body: ["Questions about this policy: tejaschoudhary1729@gmail.com"],
        },
      ]}
    />
  );
}
