"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { renameEpisode } from "@/lib/api";

function PencilIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor">
      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
    </svg>
  );
}

interface Props {
  episodeId: number;
  title: string;
  href?: string;       // if set, title is a link when not editing
}

export default function RenameEpisodeTitle({ episodeId, title: initialTitle, href }: Props) {
  const router = useRouter();
  const [title, setTitle] = useState(initialTitle);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit(e: React.MouseEvent) {
    e.preventDefault();
    setDraft(title);
    setEditing(true);
    setTimeout(() => { inputRef.current?.select(); }, 0);
  }

  async function commit() {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === title) { setEditing(false); return; }
    setSaving(true);
    try {
      await renameEpisode(episodeId, trimmed);
      setTitle(trimmed);
      router.refresh();
    } finally {
      setSaving(false);
      setEditing(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    if (e.key === "Escape") { setEditing(false); }
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        disabled={saving}
        className="w-full rounded border border-[#e53e3e]/40 bg-white/5 px-2 py-0.5 text-sm font-medium text-zinc-100 focus:outline-none focus:ring-1 focus:ring-[#e53e3e]/50 disabled:opacity-60"
      />
    );
  }

  return (
    <div className="group/rename flex min-w-0 items-center gap-1.5">
      {href ? (
        <Link href={href} className="truncate font-medium text-zinc-100 transition-colors hover:text-[#e53e3e]">
          {title}
        </Link>
      ) : (
        <span className="truncate font-medium text-zinc-500">{title}</span>
      )}
      <button
        type="button"
        onClick={startEdit}
        title="Rename"
        className="shrink-0 opacity-0 group-hover/rename:opacity-100 transition-opacity text-zinc-600 hover:text-[#e53e3e]"
      >
        <PencilIcon />
      </button>
    </div>
  );
}
