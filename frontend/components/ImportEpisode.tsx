"use client";

import { useState } from "react";
import Link from "next/link";
import { importEpisode } from "@/lib/api";

export default function ImportEpisode() {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [episodeId, setEpisodeId] = useState<number | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setStatus("loading");
    setMessage("");
    setEpisodeId(null);
    try {
      const result = await importEpisode(url.trim(), title.trim() || undefined);
      setStatus("success");
      setEpisodeId(result.episode_id);
      setMessage(result.created ? `Added "${result.title}"` : `Already linked: "${result.title}"`);
      setUrl("");
      setTitle("");
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Import failed");
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 p-5">
      <p className="mb-3 text-sm font-medium text-zinc-300">
        Add an interview or another source
      </p>
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/episode.mp3"
            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-[#e53e3e]/50 focus:outline-none focus:ring-1 focus:ring-[#e53e3e]/30"
            disabled={status === "loading"}
          />
          <button
            type="submit"
            disabled={status === "loading" || !url.trim()}
            className="rounded-lg bg-[#e53e3e] px-4 py-2 text-sm font-medium text-[#ffffff] transition hover:bg-[#f56565] disabled:opacity-40"
          >
            {status === "loading" ? "Adding…" : "Add"}
          </button>
        </div>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (optional)"
          className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-[#e53e3e]/50 focus:outline-none focus:ring-1 focus:ring-[#e53e3e]/30"
          disabled={status === "loading"}
        />
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-400" : "text-emerald-300"}`}>
          {message}
          {episodeId && (
            <Link href={`/episode/${episodeId}`} className="ml-2 text-[#e53e3e] underline hover:text-[#f56565]">
              View episode →
            </Link>
          )}
        </p>
      )}
    </div>
  );
}
