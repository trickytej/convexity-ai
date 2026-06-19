"use client";

import { useState } from "react";
import { importNewsletter } from "@/lib/api";

export default function ImportNewsletter({ onImported }: { onImported?: () => void }) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    setStatus("loading");
    setMessage("");
    try {
      const res = await importNewsletter(trimmed);
      setStatus("ok");
      setMessage(
        res.created
          ? `Added "${res.name}" — ${res.episode_count} articles discovered.`
          : `"${res.name}" already in library — ${res.episode_count} articles.`,
      );
      setUrl("");
      onImported?.();
    } catch (err: unknown) {
      setStatus("err");
      setMessage(err instanceof Error ? err.message : "Import failed");
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 p-6">
      <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-[#00d4ff]">
        Add newsletter
      </p>
      <p className="mt-1.5 text-sm text-zinc-400">
        Paste a newsletter RSS feed URL to start extracting insights from its articles.
      </p>
      <form onSubmit={handleSubmit} className="mt-4 flex gap-3">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.substack.com/feed"
          required
          className="min-w-0 flex-1 rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-[#00d4ff]/40 focus:outline-none focus:ring-1 focus:ring-[#00d4ff]/30"
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="shrink-0 rounded-lg bg-[#00d4ff] px-4 py-2 text-sm font-medium text-[#001a26] transition hover:bg-[#33ddff] disabled:opacity-50"
        >
          {status === "loading" ? "Adding…" : "Add feed"}
        </button>
      </form>
      {message && (
        <p
          className={`mt-3 text-sm ${status === "err" ? "text-rose-400" : "text-emerald-400"}`}
        >
          {message}
        </p>
      )}
    </div>
  );
}
