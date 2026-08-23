"use client";

import RiskBadge from "@/components/RiskBadge";
import type { DecisionEvent } from "@/lib/types";

function scoreColor(score: number | null): string {
  if (score === null) return "bg-slate-500";
  if (score >= 0.85) return "bg-rose-500";
  if (score >= 0.45) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function TxnCard({ decision }: { decision: DecisionEvent }) {
  const txn = decision.transaction;
  const score = decision.risk_score;
  const ruleReasons = (decision.reasons || []).filter((r) => r.source === "rule" || r.source === "gate");

  return (
    <div className="rounded-xl border border-edge bg-panel p-4 transition-shadow hover:shadow-lg hover:shadow-black/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">
            ₹{(txn.amount ?? 0).toLocaleString("en-IN")}{" "}
            <span className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-slate-300">
              {txn.payment_method ?? "?"}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-slate-400">
            {txn.customer_id} → {txn.merchant_id} · {txn.channel} ·{" "}
            {new Date(txn.event_time).toLocaleTimeString("en-IN")}
          </div>
        </div>
        <RiskBadge action={decision.action} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span className="w-14 text-[10px] uppercase text-slate-500">risk</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full ${scoreColor(score)}`}
            style={{ width: `${Math.round((score ?? 0) * 100)}%` }}
          />
        </div>
        <span className="w-12 text-right text-xs font-mono text-slate-300">
          {score === null ? "n/a" : score.toFixed(2)}
        </span>
        <span className="text-[10px] text-slate-500">{decision.latency_ms?.toFixed?.(1) ?? "—"}ms</span>
      </div>

      {ruleReasons.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {ruleReasons.slice(0, 4).map((r, i) => (
            <span
              key={`${decision.decision_id}-r-${i}`}
              title={r.description}
              className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-orange-300"
            >
              {r.code}
            </span>
          ))}
        </div>
      )}

      {decision.explanation && (
        <p className="mt-3 border-t border-edge pt-2 text-xs leading-relaxed text-slate-300">
          {decision.explanation}
          {decision.explanation_source?.startsWith("llm") && (
            <span className="ml-1 rounded bg-indigo-500/20 px-1 text-[9px] text-indigo-300">LLM</span>
          )}
        </p>
      )}
    </div>
  );
}
