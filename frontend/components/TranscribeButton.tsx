"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { processEpisode, getEpisodeStatus, resetEpisode } from "@/lib/api";

type Phase = "idle" | "starting" | "acquiring" | "transcribing" | "insights" | "done" | "error";

const PHASE_LABEL_BASE: Record<Phase, string> = {
  idle:        "__IDLE__",
  starting:    "Starting…",
  acquiring:   "Downloading…",
  transcribing:"__ACQUIRED__",
  insights:    "Extracting insights…",
  done:        "Done",
  error:       "Failed",
};

const STALE_ACQUIRED_MS = 5 * 60 * 1000; // 5 min with no DB update → job is dead

export default function TranscribeButton({
  episodeId,
  initialStatus,
  idleLabel = "Transcribe",
  acquiredLabel = "Transcribing…",
}: {
  episodeId: number;
  initialStatus?: string | null;
  idleLabel?: string;
  acquiredLabel?: string;
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCountRef = useRef(0);

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

  function markStuck(msg = "Timed out — click to retry") {
    setPhase("error");
    setErrorMsg(msg);
    stopPolling();
  }

  function startPolling() {
    stopPolling();
    pollCountRef.current = 0;
    pollRef.current = setInterval(async () => {
      pollCountRef.current += 1;
      // Hard timeout: 150 polls × 4 s = 10 min. If still acquired, job died.
      if (pollCountRef.current > 150) {
        markStuck();
        return;
      }
      try {
        const s = await getEpisodeStatus(episodeId);
        if (s.status === "transcribed" && s.nugget_count > 0) {
          setPhase("done");
          stopPolling();
          router.refresh();
        } else if (s.status === "transcribed") {
          setPhase("insights");
        } else if (s.status === "acquired") {
          // Fast-detect dead job: if updated_at is > 5 min ago and we're on the first poll,
          // the job was killed before we even started polling this session.
          if (pollCountRef.current === 1 && s.updated_at) {
            const age = Date.now() - new Date(s.updated_at).getTime();
            if (age > STALE_ACQUIRED_MS) {
              markStuck("Job interrupted — click to retry");
              return;
            }
          }
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
      // If the episode is stuck at ACQUIRED (dead job), reset it first so the
      // backend re-runs acquire rather than skipping straight to transcribe
      // with a potentially corrupt / incomplete audio file.
      if (phase === "error") {
        try { await resetEpisode(episodeId); } catch { /* non-fatal */ }
      }
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
  const PHASE_LABEL = { ...PHASE_LABEL_BASE, idle: idleLabel, transcribing: acquiredLabel };
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
            ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25"
            : phase === "error"
            ? "bg-rose-500/10 text-rose-300 ring-rose-500/25 cursor-pointer"
            : isRunning
            ? "bg-[#00d4ff]/10 text-[#00d4ff] ring-[#00d4ff]/25"
            : "bg-white/[0.06] text-zinc-300 ring-white/10 hover:bg-[#00d4ff]/10 hover:text-[#00d4ff] hover:ring-[#00d4ff]/30 cursor-pointer"
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
        <span className="text-xs text-rose-400 max-w-xs truncate" title={errorMsg}>{errorMsg}</span>
      )}
    </div>
  );
}
