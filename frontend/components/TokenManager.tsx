"use client";

import { useEffect, useState } from "react";
import type { ApiToken } from "@/lib/api";
import { createToken, listTokens, revokeToken } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export default function TokenManager({ apiUrl }: { apiUrl: string }) {
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [name, setName] = useState("Claude");
  const [fresh, setFresh] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = () => listTokens().then((r) => setTokens(r.tokens)).catch(() => setError("Could not load tokens."));
  useEffect(() => {
    refresh();
  }, []);

  async function create() {
    setError("");
    try {
      const res = await createToken(name.trim() || "token");
      setFresh(res.token);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create token");
    }
  }

  async function revoke(id: number) {
    setTokens((t) => t.filter((x) => x.id !== id));
    await revokeToken(id).catch(refresh);
  }

  const config = JSON.stringify(
    {
      mcpServers: {
        convexity: {
          command: "convexity-mcp",
          env: { CONVEXITY_API_URL: apiUrl, CONVEXITY_TOKEN: fresh ?? "cvx_…" },
        },
      },
    },
    null,
    2,
  );

  return (
    <div className="space-y-10">
      <section>
        <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">API tokens</p>
        <div className="mt-4 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Token name"
            className="w-64 rounded-lg border border-white/[0.08] bg-[#0b0c10] px-3 py-1.5 text-[13px] text-zinc-200 outline-none focus:border-[#00d4ff]/40"
          />
          <button
            onClick={create}
            className="rounded-full bg-[#00d4ff]/90 px-4 py-1.5 text-[12px] font-semibold text-black transition hover:bg-[#00d4ff]"
          >
            Create token
          </button>
        </div>
        {error && <p className="mt-3 text-[12px] text-rose-400">{error}</p>}
        {fresh && (
          <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/[0.05] p-4">
            <p className="text-[12px] text-amber-300">Copy this token now — it won&apos;t be shown again.</p>
            <code className="mt-2 block break-all font-[family-name:var(--font-mono)] text-[13px] text-zinc-100">{fresh}</code>
          </div>
        )}
        <ul className="mt-5 divide-y divide-white/[0.06]">
          {tokens.map((t) => (
            <li key={t.id} className="flex items-center gap-4 py-2.5 text-[13px]">
              <span className="text-zinc-200">{t.name}</span>
              <code className="font-[family-name:var(--font-mono)] text-[12px] text-zinc-600">{t.prefix}…</code>
              <span className="text-[11px] text-zinc-600">
                created {fmtDate(t.created_at)}
                {t.last_used_at ? ` · last used ${fmtDate(t.last_used_at)}` : " · never used"}
              </span>
              <button onClick={() => revoke(t.id)} className="ml-auto text-[12px] text-zinc-700 transition hover:text-rose-400">
                Revoke
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">MCP setup</p>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-[13px] leading-relaxed text-zinc-400">
          <li>
            Install the server from a checkout of the ConvexityAI repo:{" "}
            <code className="text-zinc-200">pip install -e .</code> (or <code className="text-zinc-200">uv sync</code>) provides the{" "}
            <code className="text-zinc-200">convexity-mcp</code> command — use its full path in the config if it isn&apos;t on your PATH.
          </li>
          <li>Create a token above.</li>
          <li>Add this to your Claude Desktop / Claude Code MCP config:</li>
        </ol>
        <pre className="mt-3 overflow-x-auto rounded-xl border border-white/[0.08] bg-[#07080b] p-4 font-[family-name:var(--font-mono)] text-[12px] leading-relaxed text-zinc-300">
          {config}
        </pre>
        <p className="mt-3 text-[12px] text-zinc-600">
          Tools: get_board, get_brief, get_security, add_question, decide, add_research.
        </p>
      </section>
    </div>
  );
}
