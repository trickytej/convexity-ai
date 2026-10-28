import Link from "next/link";

/** Invitation shown to signed-out demo visitors where a page is personal. */
export default function SignInCard({
  title,
  text,
  callbackUrl,
  cta = "Sign in free",
  href,
}: {
  title: string;
  text: string;
  callbackUrl: string;
  cta?: string;
  href?: string;
}) {
  return (
    <div className="max-w-2xl rounded-2xl border border-[#00d4ff]/30 bg-[#00d4ff]/[0.04] p-8">
      <p className="text-xl font-light text-zinc-50 [font-family:var(--font-display)]">{title}</p>
      <p className="mt-2 text-[14px] leading-relaxed text-zinc-400">{text}</p>
      <Link
        href={href ?? `/signin?callbackUrl=${encodeURIComponent(callbackUrl)}`}
        className="mt-5 inline-block rounded-full bg-[#00d4ff] px-5 py-2 text-[13px] font-medium text-[#001a26] transition hover:bg-[#33ddff]"
      >
        {cta}
      </Link>
    </div>
  );
}
