import TokenManager from "@/components/TokenManager";
import SignInCard from "@/components/SignInCard";
import { auth } from "@/auth";

export const dynamic = "force-dynamic";
export const metadata = { title: "API — ConvexityAI" };

export default async function DevelopersPage() {
  const signedIn = !!(await auth())?.user?.id;
  // The MCP server talks to the API directly with a personal token.
  const apiUrl = process.env.PUBLIC_API_URL ?? process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">API</span>
      </p>
      <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
        Connect <span className="text-[#00d4ff]">your agents</span>
      </h1>
      <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-zinc-500">
        The ConvexityAI MCP server lets Claude (or any MCP client) read your board and brief,
        add questions, keep or drop developments, and push your own research in. It
        authenticates with a personal token.
      </p>
      <div className="mt-10 max-w-3xl">
        {signedIn ? (
          <TokenManager apiUrl={apiUrl} />
        ) : (
          <SignInCard
            title="Create your personal API token"
            text="Tokens are tied to your account. Sign in free to connect Claude or any MCP client to your own board, Brief and research."
            callbackUrl="/developers"
          />
        )}
      </div>
    </div>
  );
}
