import LegalPage from "@/components/LegalPage";

export const metadata = { title: "Terms — ConvexityAI" };

export default function TermsPage() {
  return (
    <LegalPage
      eyebrow="Terms"
      title="Terms of service"
      updated="October 15, 2026"
      sections={[
        {
          heading: "The service",
          body: [
            "ConvexityAI is a research tool that organizes public information and your own notes against the questions you track. It is provided as-is, may change, and may be unavailable at times.",
          ],
        },
        {
          heading: "Not investment advice",
          body: [
            "Nothing in ConvexityAI is investment advice or a recommendation to buy or sell any security. Insights, signals and model figures are generated automatically, can be incomplete or wrong, and should be verified before you rely on them. You are responsible for your own investment decisions.",
          ],
        },
        {
          heading: "Your account and content",
          body: [
            "You are responsible for activity under your account and for keeping your API tokens secret. You keep ownership of research you upload and confirm you have the right to upload it.",
          ],
        },
        {
          heading: "Acceptable use",
          body: [
            "Don't misuse the service: no attempts to access other users' data, overload or reverse-engineer the service, or resell access without permission.",
          ],
        },
        {
          heading: "Contact",
          body: ["tejaschoudhary1729@gmail.com"],
        },
      ]}
    />
  );
}
