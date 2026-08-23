"use client";

import { useCallback, useEffect, useState } from "react";

import RiskBadge from "@/components/RiskBadge";
import { api } from "@/lib/api";
import type { DecisionEvent } from "@/lib/types";

interface QueueItem extends DecisionEvent {
  review: { id: number; status: string; created_at: string };
}

export default function ReviewQueue() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [followups, setFollowups] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ items: QueueItem[] }>("/api/v1/queue")
      .then((r) => setItems(r.items))
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  async function resolve(reviewId: number, outcome: "fraud" | "legitimate") {
    try {
      const res = await api<{ suggested_followup: string | null }>(
        `/api/v1/queue/${reviewId}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({ outcome, analyst: "ops-user", notes: notes[reviewId] ?? "" }),
        },
      );
      if (res.suggested_followup) {
        setFollowups((f) => ({ ...f, [reviewId]: res.suggested_followup as string }));
      }
      load();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-bold">Human Review Queue</h1>
        <p className="text-xs text-slate-400">
          Medium-risk transactions held for analysts · resolutions feed the retraining dataset
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>
      )}

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-edge p-10 text-center text-sm text-slate-500">
          Queue is clear.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.decision_id} className="rounded-xl border border-edge bg-panel p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold">₹{(item.transaction.amount ?? 0).toLocaleString("en-IN")}</span>
                  <span className="ml-2 text-xs text-slate-400">
                    {item.transaction.customer_id} → {item.transaction.merchant_id} · score{" "}
                    <b>{(item.risk_score ?? 0).toFixed(2)}</b> · {new Date(item.created_at).toLocaleTimeString("en-IN")}
                  </span>
                </div>
                <RiskBadge action={item.action} />
              </div>

              {(item.reasons || []).filter((r) => r.source !== "model").slice(0, 3).map((r, i) => (
                <p key={i} className="mt-1.5 text-xs text-orange-300">
                  • [{r.code}] {r.description}
                </p>
              ))}

              {item.explanation && (
                <p className="mt-2 text-xs leading-relaxed text-slate-300">{item.explanation}</p>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  value={notes[item.decision_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [item.decision_id]: e.target.value }))}
                  placeholder="analyst notes (optional)"
                  className="w-64 rounded-md border border-edge bg-surface px-2 py-1.5 text-xs outline-none focus:border-sky-500"
                />
                <button
                  onClick={() => resolve(item.review.id, "fraud")}
                  className="rounded-md bg-rose-500/90 px-3 py-1.5 text-xs font-semibold hover:bg-rose-500"
                >
                  Confirm Fraud
                </button>
                <button
                  onClick={() => resolve(item.review.id, "legitimate")}
                  className="rounded-md bg-emerald-600/90 px-3 py-1.5 text-xs font-semibold hover:bg-emerald-600"
                >
                  Approve Legitimate
                </button>
              </div>

              {followups[item.decision_id] && (
                <p className="mt-2 rounded-md bg-indigo-500/10 p-2 text-xs text-indigo-200">
                  AI follow-up: {followups[item.decision_id]}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
