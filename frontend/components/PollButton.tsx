"use client";

import { useState } from "react";
import { pollShow } from "@/lib/api";

export default function PollButton({ slug, dark = false }: { slug: string; dark?: boolean }) {
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleClick(e: React.MouseEvent) {
    e.preventDefault(); // don't navigate the card link
    if (status === "loading") return;
    setStatus("loading");
    setMessage("");
    try {
      const r = await pollShow(slug);
      setStatus("done");
      setMessage(r.new > 0 ? `+${r.new} new` : "Up to date");
    } catch (err) {
      setStatus("error");
      setMessage("Failed");
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      title="Refresh episode list from RSS"
      className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition-all print:hidden ${
        status === "done"
          ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
          : status === "error"
          ? "bg-rose-50 text-rose-600 ring-rose-200"
          : dark
          ? "bg-white/10 text-white/80 ring-white/20 hover:bg-white/20 hover:text-white"
          : "bg-zinc-50 text-zinc-500 ring-zinc-200 hover:bg-zinc-100 hover:text-zinc-700"
      }`}
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 16 16"
        fill="currentColor"
        className={status === "loading" ? "animate-spin" : ""}
      >
        <path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/>
        <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/>
      </svg>
      {status === "idle" || status === "loading" ? (status === "loading" ? "Refreshing…" : "Refresh") : message}
    </button>
  );
}
