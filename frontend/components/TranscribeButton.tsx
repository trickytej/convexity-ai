"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { processEpisode, getEpisodeStatus } from "@/lib/api";

type Phase = "idle" | "starting" | "acquiring" | "transcribing" | "insights" | "done" | "error";

const PHASE_LABEL: Record<Phase, string> = {
  idle:        "Transcribe",
  starting:    "Starting…",
  acquiring:   "Downloading…",
  transcribing:"Transcribing…",
  insights:    "Extracting insights…",
  done:        "Done",
  error:       "Failed",
};

export default function TranscribeButton({ episodeId, initialStatus }: { episodeId: number; initialStatus?: string | null }) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // If already being processed on mount (e.g. page refresh mid-job), start polling
  useEffect(() => {
    if (initialStatus === "acquired") {
      setPhase("transcribing");
      startPolling();
    }
    return () => stopPolling();
  }, []);

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }

  function startPolling() {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getEpisodeStatus(episodeId);
        if (s.status === "transcribed" && s.nugget_count > 0) {
          setPhase("done");
          stopPolling();
          router.refresh();
        } else if (s.status === "transcribed") {
          setPhase("insights");
        } else if (s.status === "acquired") {
          setPhase("transcribing");
        } else if (s.status === "failed") {
          setPhase("error");
          setErrorMsg(s.error ?? "Pipeline failed");
          stopPolling();
        }
      } catch { /* network blip, keep polling */ }
    }, 4000);
  }

  async function handleClick() {
    if (phase !== "idle" && phase !== "error") return;
    setPhase("starting");
    setErrorMsg("");
    try {
      const res = await processEpisode(episodeId);
      if (res.status === "already_done") {
        setPhase("done");
        router.refresh();
        return;
      }
      setPhase("acquiring");
      startPolling();
    } catch (e) {
      setPhase("error");
      setErrorMsg(e instanceof Error ? e.message : "Failed to start");
    }
  }

  const isRunning = ["starting", "acquiring", "transcribing", "insights"].includes(phase);
  const label = PHASE_LABEL[phase];

  return (
    <div className="flex items-center gap-2 shrink-0">
      <button
        type="button"
        onClick={handleClick}
        disabled={isRunning || phase === "done"}
        title={errorMsg || undefined}
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-all ${
          phase === "done"
            ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
            : phase === "error"
            ? "bg-rose-50 text-rose-600 ring-rose-200 cursor-pointer"
            : isRunning
            ? "bg-indigo-50 text-indigo-600 ring-indigo-200"
            : "bg-white text-zinc-700 ring-zinc-300 hover:bg-indigo-50 hover:text-indigo-700 hover:ring-indigo-300 cursor-pointer"
        }`}
      >
        {isRunning && (
          <svg className="animate-spin" width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/>
            <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/>
          </svg>
        )}
        {label}
      </button>
      {phase === "error" && errorMsg && (
        <span className="text-xs text-rose-500 max-w-xs truncate" title={errorMsg}>{errorMsg}</span>
      )}
    </div>
  );
}
