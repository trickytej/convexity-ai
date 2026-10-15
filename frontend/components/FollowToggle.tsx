"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { followSecurity, unfollowSecurity } from "@/lib/api";

export default function FollowToggle({ company, followed }: { company: string; followed: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    try {
      await (followed ? unfollowSecurity(company) : followSecurity(company));
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className={`rounded-full border px-3.5 py-1.5 text-[12px] font-medium transition disabled:opacity-50 ${
        followed
          ? "border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff] hover:border-rose-500/40 hover:text-rose-300"
          : "border-white/[0.1] text-zinc-300 hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
      }`}
    >
      {followed ? "Following" : "+ Follow"}
    </button>
  );
}
