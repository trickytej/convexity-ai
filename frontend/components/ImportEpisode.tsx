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
    <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-5">
      <p className="mb-3 text-sm font-medium text-zinc-700">Add an interview or another source</p>
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/episode.mp3"
            className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-sm placeholder:text-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            disabled={status === "loading"}
          />
          <button
            type="submit"
            disabled={status === "loading" || !url.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {status === "loading" ? "Adding…" : "Add"}
          </button>
        </div>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (optional)"
          className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm placeholder:text-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          disabled={status === "loading"}
        />
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-600" : "text-emerald-600"}`}>
          {message}
          {episodeId && (
            <Link href={`/episode/${episodeId}`} className="ml-2 underline hover:text-emerald-700">
              View episode →
            </Link>
          )}
        </p>
      )}
    </div>
  );
}
