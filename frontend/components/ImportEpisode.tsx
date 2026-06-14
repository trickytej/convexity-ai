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

  const inputStyle = {
    backgroundColor: "rgba(255,255,255,0.1)",
    border: "1px solid rgba(255,255,255,0.2)",
    color: "white",
  };

  return (
    <div className="rounded-xl p-5" style={{ backgroundColor: "rgb(45, 45, 90)" }}>
      <p className="mb-3 text-sm font-medium" style={{ color: "rgba(255,255,255,0.85)" }}>
        Add an interview or another source
      </p>
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/episode.mp3"
            className="flex-1 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1"
            style={inputStyle}
            disabled={status === "loading"}
          />
          <button
            type="submit"
            disabled={status === "loading" || !url.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50"
            style={{ backgroundColor: "white", color: "rgb(45, 45, 90)" }}
          >
            {status === "loading" ? "Adding…" : "Add"}
          </button>
        </div>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (optional)"
          className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1"
          style={inputStyle}
          disabled={status === "loading"}
        />
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-300" : "text-emerald-300"}`}>
          {message}
          {episodeId && (
            <Link href={`/episode/${episodeId}`} className="ml-2 underline hover:opacity-80">
              View episode →
            </Link>
          )}
        </p>
      )}
    </div>
  );
}
