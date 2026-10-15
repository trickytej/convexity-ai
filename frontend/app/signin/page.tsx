import { redirect } from "next/navigation";
import { auth, DEV_LOGIN, signIn } from "@/auth";

const safeCallback = (url?: string) => (url && url.startsWith("/") && !url.startsWith("//") ? url : "/brief");

export default async function SignInPage({
  searchParams,
}: {
  searchParams?: Promise<{ callbackUrl?: string; error?: string }>;
}) {
  const params = await searchParams;
  const callbackUrl = safeCallback(params?.callbackUrl);
  const session = await auth();
  if (session?.user?.id) redirect(callbackUrl);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-sm flex-col justify-center">
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">ConvexityAI</span>
      </p>
      <h1 className="mt-5 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
        Sign in
      </h1>
      <p className="mt-3 text-[14px] leading-relaxed text-zinc-500">
        Track the questions that matter for the securities you follow.
      </p>

      {params?.error && (
        <p className="mt-4 text-[13px] text-rose-400">Sign-in failed — please try again.</p>
      )}

      <form
        className="mt-8"
        action={async () => {
          "use server";
          await signIn("google", { redirectTo: callbackUrl });
        }}
      >
        <button
          type="submit"
          className="w-full rounded-full bg-[#00d4ff]/90 px-5 py-2.5 text-[13px] font-semibold text-black transition hover:bg-[#00d4ff]"
        >
          Continue with Google
        </button>
      </form>

      {DEV_LOGIN && (
        <form
          className="mt-8 border-t border-white/[0.08] pt-6"
          action={async (form: FormData) => {
            "use server";
            await signIn("dev", { email: form.get("email"), redirectTo: callbackUrl });
          }}
        >
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-amber-400/80">
            Dev login (local only)
          </p>
          <input
            name="email"
            type="email"
            required
            placeholder="any@email.com"
            className="mt-3 w-full rounded-lg border border-white/[0.08] bg-[#0b0c10] px-3 py-2 text-[13px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
          />
          <button
            type="submit"
            className="mt-3 w-full rounded-full border border-white/[0.12] px-5 py-2 text-[13px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
          >
            Sign in as this email
          </button>
        </form>
      )}
    </div>
  );
}
