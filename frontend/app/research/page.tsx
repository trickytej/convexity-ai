"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ResearchDoc } from "@/lib/api";
import { addResearch, deleteResearch, listResearch, uploadResearch } from "@/lib/api";
import { fmtDate } from "@/lib/format";

type Mode = "paste" | "link" | "file";

const STATUS_LABEL: Record<string, string> = {
  transcribed: "Reading…",
  insights_extracted: "Matched",
  failed: "Failed",
};

export default function ResearchPage() {
  const [docs, setDocs] = useState<ResearchDoc[]>([]);
  const [mode, setMode] = useState<Mode>("paste");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    listResearch()
      .then((r) => setDocs(r.documents))
      .catch(() => setError("Could not load your research."));
  }, []);

  useEffect(refresh, [refresh]);

  // Poll while anything is still being read.
  useEffect(() => {
    if (!docs.some((d) => d.status === "transcribed")) return;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [docs, refresh]);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (mode === "file") {
        if (!file) throw new Error("Choose a file");
        await uploadResearch(file, title);
      } else if (mode === "link") {
        await addResearch({ title, url });
      } else {
        await addResearch({ title, text });
      }
      setTitle("");
      setText("");
      setUrl("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setDocs((d) => d.filter((x) => x.id !== id));
    await deleteResearch(id).catch(refresh);
  }

  const canSubmit = mode === "file" ? !!file : mode === "link" ? url.trim() !== "" : text.trim() !== "";

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Research</span>
      </p>
      <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
        Your <span className="text-[#00d4ff]">inside view</span>
      </h1>
      <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-zinc-500">
        Bring in your own notes, channel checks, call transcripts and reports. They stay private
        to you, get weighed against your questions like any other source, and show up as
        &ldquo;Inside view&rdquo; on your board.
      </p>

      <div className="mt-10 max-w-3xl rounded-2xl border border-white/[0.08] bg-[#0b0c10]/80 p-5">
        <div className="flex gap-2">
          {(["paste", "link", "file"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full border px-3 py-1 text-[12px] transition ${
                mode === m
                  ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
                  : "border-white/[0.06] text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {m === "paste" ? "Paste notes" : m === "link" ? "Add a link" : "Upload PDF / text"}
            </button>
          ))}
        </div>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (optional)"
          className="mt-4 w-full rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[13px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
        />
        {mode === "paste" && (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            placeholder="Paste notes, an expert-call write-up, or a report excerpt…"
            className="mt-3 w-full resize-y rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[13px] leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
          />
        )}
        {mode === "link" && (
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            className="mt-3 w-full rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[13px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
          />
        )}
        {mode === "file" && (
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-3 block w-full text-[12px] text-zinc-400 file:mr-3 file:rounded-full file:border-0 file:bg-white/[0.06] file:px-3 file:py-1.5 file:text-[12px] file:text-zinc-300"
          />
        )}
        <div className="mt-4 flex items-center gap-3">
          {error && <p className="text-[12px] text-rose-400">{error}</p>}
          <button
            onClick={submit}
            disabled={busy || !canSubmit}
            className="ml-auto rounded-full bg-[#00d4ff]/90 px-4 py-1.5 text-[12px] font-semibold text-black transition hover:bg-[#00d4ff] disabled:opacity-40"
          >
            {busy ? "Adding…" : "Add research"}
          </button>
        </div>
      </div>

      <div className="mt-12 max-w-3xl">
        {docs.length === 0 ? (
          <p className="text-[13px] text-zinc-600">Nothing added yet.</p>
        ) : (
          <ul className="divide-y divide-white/[0.06]">
            {docs.map((d) => (
              <li key={d.id} className="flex items-start gap-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] text-zinc-200">{d.title}</p>
                  <p className="mt-0.5 text-[11px] text-zinc-600">
                    {fmtDate(d.created_at)} · {STATUS_LABEL[d.status] ?? d.status}
                    {d.status === "insights_extracted" &&
                      ` · ${d.nugget_count} insights · ${d.signal_count} signal${d.signal_count === 1 ? "" : "s"}, ${d.hit_count - d.signal_count} reference`}
                    {d.error && <span className="text-rose-400"> · {d.error}</span>}
                  </p>
                </div>
                <button
                  onClick={() => remove(d.id)}
                  className="text-[12px] text-zinc-700 transition hover:text-rose-400"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
