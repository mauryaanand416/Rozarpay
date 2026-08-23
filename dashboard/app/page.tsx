"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import StatCard from "@/components/StatCard";
import TxnCard from "@/components/TxnCard";
import { streamUrl } from "@/lib/api";
import type { DecisionEvent } from "@/lib/types";

export default function LiveFeed() {
  const [decisions, setDecisions] = useState<DecisionEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [counts, setCounts] = useState({ ALLOW: 0, REVIEW: 0, BLOCK: 0, ESCALATE: 0 });
  const [safeMode, setSafeMode] = useState(false);
  const idRef = useRef<Map<number, DecisionEvent>>(new Map());

  useEffect(() => {
    let es: EventSource | null = null;

    try {
      es = new EventSource(streamUrl());
      es.onopen = () => setConnected(true);
      es.onerror = () => setConnected(false);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "queue_update" || data.type === "explanation") {
            if (data.type === "explanation") {
              applyExplanation(data);
            }
            return;
          }
          setSafeMode(data.model_version === "unavailable");
          const action = data.action as keyof typeof counts;
          idRef.current.set(data.decision_id, data);
          setDecisions(Array.from(idRef.current.values()).slice(-40).reverse());
          setCounts((prev) => ({ ...prev, [action]: (prev[action] ?? 0) + 1 }));
        } catch {}
      };
    } catch {}

    return () => es?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyExplanation(data: { decision_id: number; explanation: string; explanation_source: string }) {
    const existing = idRef.current.get(data.decision_id);
    if (existing) {
      const updated = { ...existing, explanation: data.explanation, explanation_source: data.explanation_source };
      idRef.current.set(data.decision_id, updated);
      setDecisions(Array.from(idRef.current.values()).slice(-40).reverse());
    }
  }

  const total = counts.ALLOW + counts.REVIEW + counts.BLOCK + counts.ESCALATE;
  const caughtValue = decisions
    .filter((d) => d.action === "BLOCK")
    .reduce((sum, d) => sum + (d.transaction.amount || 0), 0);

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Live Risk Feed</h1>
          <p className="text-xs text-slate-400">
            Streaming decisions from the risk engine · every action is explainable and audited
          </p>
        </div>
        <span
          className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
            connected
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-slate-600 bg-slate-800 text-slate-400"
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${connected ? "animate-pulse bg-emerald-400" : "bg-slate-500"}`} />
          {connected ? "streaming" : "disconnected"}
        </span>
      </header>

      {safeMode && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
          Safe mode: model artifacts not found — all transactions are routed to human review (fail-safe).
          Run the training pipeline to enable scoring.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="Processed" value={total} sub="this session" />
        <StatCard label="Allowed" value={counts.ALLOW} accent="text-emerald-300" />
        <StatCard label="In Review" value={counts.REVIEW} accent="text-amber-300" />
        <StatCard label="Blocked" value={counts.BLOCK} accent="text-rose-300" />
        <StatCard
          label="Fraud Value Stopped"
          value={`₹${Math.round(caughtValue).toLocaleString("en-IN")}`}
          accent="text-fuchsia-300"
        />
      </div>

      {decisions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-edge p-10 text-center text-sm text-slate-500">
          Waiting for transactions… start the simulator:
          <code className="mx-1 rounded bg-slate-800 px-1.5 py-0.5 text-orange-300">
            POST /api/v1/admin/simulator/start
          </code>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {decisions.map((d) => (
            <TxnCard key={d.decision_id} decision={d} />
          ))}
        </div>
      )}
    </div>
  );
}
