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
    <div className="rounded-xl p-5" style={{ backgroundColor: "rgb(45, 45, 90)" }}>
      <p className="mb-3 text-sm font-medium" style={{ color: "rgba(255,255,255,0.85)" }}>
        Add a podcast via RSS feed URL
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://feeds.example.com/podcast.rss"
          className="flex-1 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1"
          style={{
            backgroundColor: "rgba(255,255,255,0.1)",
            border: "1px solid rgba(255,255,255,0.2)",
            color: "white",
          }}
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
      </form>
      {message && (
        <p className={`mt-2 text-sm ${status === "error" ? "text-rose-300" : "text-emerald-300"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
