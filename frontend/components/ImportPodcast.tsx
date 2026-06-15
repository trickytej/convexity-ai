"use client";

import { useState } from "react";
import { importPodcast } from "@/lib/api";

export default function ImportPodcast() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setStatus("loading");
    setMessage("");
    try {
      const result = await importPodcast(url.trim());
      setStatus("success");
      setMessage(
        result.created
          ? `Added "${result.name}" — ${result.episode_count} episodes found. Refresh to see it.`
          : `"${result.name}" already linked — refreshed ${result.episode_count} episodes.`
      );
      setUrl("");
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Import failed");
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 p-5">
      <p className="mb-3 text-sm font-medium text-zinc-300">
        Add a podcast via RSS feed URL
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://feeds.example.com/podcast.rss"
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-[#1ec997]/50 focus:outline-none focus:ring-1 focus:ring-[#1ec997]/30"
          disabled={status === "loading"}
        />
        <button
          type="submit"
          disabled={status === "loading" || !url.trim()}
          className="rounded-lg bg-[#1ec997] px-4 py-2 text-sm font-medium text-[#06160f] transition hover:bg-[#34d6a8] disabled:opacity-40"
        >
          {status === "loading" ? "Adding…" : "Add"}
        </button>
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-400" : "text-emerald-300"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
