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
    <div className="rounded-xl border border-zinc-200 bg-white p-5">
      <p className="mb-3 text-sm font-medium text-zinc-700">
        Add a podcast via RSS feed URL
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://feeds.example.com/podcast.rss"
          className="flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-300"
          disabled={status === "loading"}
        />
        <button
          type="submit"
          disabled={status === "loading" || !url.trim()}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-40"
        >
          {status === "loading" ? "Adding…" : "Add"}
        </button>
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-600" : "text-emerald-600"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
