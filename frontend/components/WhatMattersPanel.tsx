"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { SecurityModel } from "@/lib/api";
import { adoptHouseQuestions } from "@/lib/api";
import QuestionsEditor from "@/components/QuestionsEditor";

/** The user's questions, plus ConvexityAI's defaults: users can adopt them;
 * admins can edit them (they're what new followers start from). */
export default function WhatMattersPanel({ model, isAdmin }: { model: SecurityModel; isAdmin: boolean }) {
  const router = useRouter();
  const [tab, setTab] = useState<"mine" | "house">("mine");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const house = model.house_questions;
  const sameAsHouse =
    house.length > 0 &&
    house.length === model.questions.length &&
    house.every((h, i) => h.question === model.questions[i]?.question);

  async function adopt() {
    setBusy(true);
    try {
      await adoptHouseQuestions(model.key);
      setConfirming(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  const tabCls = (active: boolean) =>
    `rounded-full border px-3 py-1 text-[12px] transition ${
      active ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]" : "border-white/[0.06] text-zinc-500 hover:text-zinc-300"
    }`;

  return (
    <div>
      {isAdmin && (
        <div className="mb-4 flex items-center gap-2">
          <button onClick={() => setTab("mine")} className={tabCls(tab === "mine")}>
            Your questions
          </button>
          <button onClick={() => setTab("house")} className={tabCls(tab === "house")}>
            ConvexityAI defaults · {house.length}
          </button>
        </div>
      )}

      {tab === "house" ? (
        <div>
          <p className="mb-3 text-[12px] text-zinc-500">
            Every user who follows {model.company} starts from these questions (and the evidence already matched
            to them). Changing them doesn&apos;t affect anyone&apos;s existing copy.
          </p>
          <QuestionsEditor
            key="house"
            company={model.company}
            ticker={model.ticker}
            initial={house}
            asHouse
            canDraft={isAdmin}
          />
        </div>
      ) : (
        <div>
          <QuestionsEditor
            key="mine"
            company={model.company}
            ticker={model.ticker}
            initial={model.questions}
            canDraft={isAdmin}
          />
          {house.length > 0 && !sameAsHouse && (
            <div className="mt-4 text-[12px] text-zinc-500">
              {confirming ? (
                <span className="flex flex-wrap items-center gap-3">
                  {model.questions.length > 0
                    ? "Replace your questions with ConvexityAI's? Your current set is archived."
                    : `Start from ConvexityAI's ${house.length} questions?`}
                  <button
                    onClick={adopt}
                    disabled={busy}
                    className="rounded-full bg-[#00d4ff]/90 px-3 py-1 font-semibold text-black hover:bg-[#00d4ff] disabled:opacity-50"
                  >
                    {busy ? "Copying…" : "Yes, use them"}
                  </button>
                  <button onClick={() => setConfirming(false)} className="hover:text-zinc-300">
                    Cancel
                  </button>
                </span>
              ) : (
                <button onClick={() => setConfirming(true)} className="transition hover:text-[#00d4ff]">
                  {model.questions.length > 0
                    ? `Reset to ConvexityAI's questions (${house.length}) →`
                    : `Use ConvexityAI's questions (${house.length}) →`}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
