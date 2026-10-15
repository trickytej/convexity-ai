import { getBoard, getUniverse } from "@/lib/api";
import Board from "@/components/Board";
import FollowPicker from "@/components/FollowPicker";

export const dynamic = "force-dynamic";

export default async function ModelPage() {
  const [{ categories }, { securities }] = await Promise.all([getUniverse(), getBoard()]);

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Model</span>
      </p>
      <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
        Your <span className="text-[#00d4ff]">securities</span>
      </h1>
      <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-zinc-500">
        Each security carries the 4–5 questions that decide it. New research is weighed
        against them daily; what you keep builds the security&apos;s tracker.
      </p>

      {securities.length === 0 ? (
        <p className="mt-10 text-[14px] text-zinc-500">
          You&apos;re not following anything yet — pick securities below.
        </p>
      ) : (
        <div className="mt-10">
          <Board securities={securities} />
          <p className="mt-6 text-[11px] leading-relaxed text-zinc-600">
            Status weighs the last 30 days of signals — strong, high-quality evidence only.
            Green: evidence supports the thesis · Red: it contradicts · Amber: mixed · Grey: no signals.
          </p>
        </div>
      )}

      <section className="mt-16 border-t border-white/[0.08] pt-10">
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
          <span className="text-zinc-500">Follow securities</span>
        </p>
        <div className="mt-6">
          <FollowPicker categories={categories} />
        </div>
      </section>
    </div>
  );
}
