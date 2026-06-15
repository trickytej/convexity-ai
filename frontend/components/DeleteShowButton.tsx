"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteShow } from "@/lib/api";

export default function DeleteShowButton({ slug }: { slug: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function handleConfirmClick(e: React.MouseEvent) {
    e.preventDefault();
    setConfirming(true);
  }

  function handleCancel(e: React.MouseEvent) {
    e.preventDefault();
    setConfirming(false);
  }

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    setDeleting(true);
    try {
      await deleteShow(slug);
      router.refresh();
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  }

  if (confirming) {
    return (
      <div className="flex items-center gap-2" onClick={(e) => e.preventDefault()}>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-50 transition-opacity"
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <span className="text-zinc-600">·</span>
        <button
          onClick={handleCancel}
          className="text-xs text-zinc-400 hover:text-zinc-200 transition-opacity"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleConfirmClick}
      title="Remove podcast"
      className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600 hover:text-rose-400"
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
        <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
        <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
      </svg>
    </button>
  );
}
