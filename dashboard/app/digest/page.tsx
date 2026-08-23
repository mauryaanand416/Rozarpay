"use client";

import { useState } from "react";

import { api } from "@/lib/api";

interface DigestResponse {
  id: number;
  content: string;
  source: string;
  stats: {
    window_hours: number;
    total_transactions: number;
    by_action: Record<string, number>;
    top_rule_hits: Record<string, number>;
    blocked_or_escalated_value_inr: number;
  };
}

export default function DigestPage() {
  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await api<DigestResponse>("/api/v1/admin/digest/generate?hours=24", { method: "POST" });
      setDigest(res);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Merchant Risk Digest</h1>
          <p className="text-xs text-slate-400">
            LLM-generated daily summary of your risk posture (falls back to statistical digest without an LLM key)
          </p>
        </div>
        <button
          onClick={generate}
          disabled={loading}
          className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
        >
          {loading ? "Generating…" : "Generate 24h Digest"}
        </button>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>
      )}

      {digest && (
        <div className="rounded-xl border border-edge bg-panel p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="rounded bg-indigo-500/15 px-2 py-0.5 text-[10px] uppercase text-indigo-300">
              source: {digest.source}
            </span>
            <span className="text-[11px] text-slate-500">
              {digest.stats.total_transactions} txns · window {digest.stats.window_hours}h
            </span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-200">{digest.content}</pre>

          {Object.keys(digest.stats.top_rule_hits ?? {}).length > 0 && (
            <div className="mt-4 border-t border-edge pt-3">
              <div className="mb-1.5 text-[10px] uppercase tracking-wide text-slate-500">Top rule signals</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(digest.stats.top_rule_hits).map(([code, count]) => (
                  <span key={code} className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-orange-300">
                    {code} ×{count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!digest && !error && (
        <div className="rounded-xl border border-dashed border-edge p-10 text-center text-sm text-slate-500">
          No digest yet — generate one after running the simulator for a few minutes.
        </div>
      )}
    </div>
  );
}
