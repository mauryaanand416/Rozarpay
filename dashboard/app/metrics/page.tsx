"use client";

import { useEffect, useState } from "react";

import StatCard from "@/components/StatCard";
import { api } from "@/lib/api";
import type { LiveStats, ModelMetrics } from "@/lib/types";

interface Drift {
  status: string;
  psi_by_feature?: Record<string, number>;
  alerts?: string[];
  samples?: number;
}

function ConfusionMatrix({ cm }: { cm: { tp: number; fp: number; fn: number; tn: number } }) {
  const cells = [
    { label: "True Positive", v: cm.tp, cls: "bg-emerald-500/15 text-emerald-300" },
    { label: "False Positive", v: cm.fp, cls: "bg-amber-500/15 text-amber-300" },
    { label: "False Negative", v: cm.fn, cls: "bg-rose-500/15 text-rose-300" },
    { label: "True Negative", v: cm.tn, cls: "bg-slate-700/40 text-slate-300" },
  ];
  return (
    <div className="grid grid-cols-2 gap-2">
      {cells.map((c) => (
        <div key={c.label} className={`rounded-lg p-3 ${c.cls}`}>
          <div className="text-[10px] uppercase tracking-wide opacity-80">{c.label}</div>
          <div className="text-xl font-bold">{c.v.toLocaleString("en-IN")}</div>
        </div>
      ))}
    </div>
  );
}

export default function MetricsPage() {
  const [model, setModel] = useState<ModelMetrics | null>(null);
  const [live, setLive] = useState<LiveStats | null>(null);
  const [drift, setDrift] = useState<Drift | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<ModelMetrics>("/api/v1/metrics/model"),
      api<LiveStats>("/api/v1/metrics/live"),
      api<Drift>("/api/v1/metrics/drift"),
    ])
      .then(([m, l, d]) => {
        setModel(m);
        setLive(l);
        setDrift(d);
      })
      .catch((e) => setError(String((e as Error).message || e)));
  }, []);

  if (error)
    return <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>;
  if (!model) return <p className="text-sm text-slate-400">Loading metrics…</p>;
  if (!model.pr_auc)
    return (
      <div className="rounded-xl border border-dashed border-edge p-10 text-center text-sm text-slate-500">
        Model not trained yet. Run: <code className="mx-1 rounded bg-slate-800 px-1.5 py-0.5 text-orange-300">python -m app.ml.train</code>
      </div>
    );

  const review = model.review_threshold!;
  const block = model.block_threshold;
  const importance = Object.entries(model.feature_importance_gain ?? {}).slice(0, 8);
  const maxImp = Math.max(...importance.map(([, v]) => v), 1);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold">Model Metrics</h1>
        <p className="text-xs text-slate-400">
          {model.model_version} · {model.dataset_rows?.toLocaleString("en-IN")} txns · fraud rate{" "}
          {(100 * (model.fraud_rate ?? 0)).toFixed(2)}% · split: {model.split?.strategy}
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="PR-AUC" value={model.pr_auc} sub={`ROC-AUC ${model.roc_auc}`} accent="text-sky-300" />
        <StatCard
          label="Precision @review"
          value={`${(review.precision * 100).toFixed(1)}%`}
          sub={`recall ${(review.recall * 100).toFixed(1)}%`}
          accent="text-emerald-300"
        />
        <StatCard
          label="Recall @review"
          value={`${(review.recall * 100).toFixed(1)}%`}
          sub={`F1 ${review.f1.toFixed(3)} · F2 ${review.f2.toFixed(3)}`}
          accent="text-amber-300"
        />
        <StatCard label="Calibration (Brier)" value={model.brier ?? "—"} sub="lower is better" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-edge bg-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">
            Confusion matrix @ t_review={review.threshold.toFixed(3)}
            <span className="ml-2 text-xs font-normal text-slate-500">held-out time-based test set</span>
          </h2>
          <ConfusionMatrix cm={review.confusion_matrix} />
        </section>

        <section className="rounded-xl border border-edge bg-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Operating thresholds</h2>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between rounded bg-slate-800/60 px-3 py-2">
              <span>t_review (route to human queue)</span>
              <b>{review.threshold.toFixed(3)}</b>
            </div>
            {block && (
              <div className="flex justify-between rounded bg-slate-800/60 px-3 py-2">
                <span>t_block (auto-block tier)</span>
                <b>{block.threshold.toFixed(3)}</b>
              </div>
            )}
            {block && (
              <div className="flex justify-between rounded bg-slate-800/60 px-3 py-2">
                <span>Precision at block tier</span>
                <b className={(block.precision >= 0.9 ? "text-emerald-300" : "text-amber-300")}>
                  {(block.precision * 100).toFixed(1)}%
                </b>
              </div>
            )}
            {model.cost_optimal_threshold && (
              <div className="flex justify-between rounded bg-slate-800/60 px-3 py-2">
                <span>₹ cost-optimal threshold</span>
                <b>{model.cost_optimal_threshold.threshold.toFixed(3)}</b>
              </div>
            )}
            {model.cost_optimal_threshold && (
              <div className="flex justify-between rounded bg-slate-800/60 px-3 py-2">
                <span>Fraud ₹ value recall</span>
                <b>{(model.cost_optimal_threshold.value_recall * 100).toFixed(1)}%</b>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-edge bg-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Top features (gain)</h2>
          <div className="space-y-1.5">
            {importance.map(([name, val]) => (
              <div key={name} className="flex items-center gap-2 text-[11px]">
                <span className="w-44 truncate text-slate-400" title={name}>
                  {name}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
                  <div className="h-full bg-sky-500/70" style={{ width: `${(val / maxImp) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-edge bg-panel p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            Drift monitor (PSI)
            {drift?.status === "alert" ? (
              <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[10px] text-rose-300">ALERT</span>
            ) : drift?.status === "healthy" ? (
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] text-emerald-300">healthy</span>
            ) : null}
          </h2>
          <div className="space-y-1.5 text-[11px]">
            {Object.entries(drift?.psi_by_feature ?? {}).map(([name, score]) => (
              <div key={name} className="flex items-center gap-2">
                <span className="w-44 truncate text-slate-400">{name}</span>
                <span className={`font-mono ${score > 0.25 ? "text-rose-300" : score > 0.1 ? "text-amber-300" : "text-slate-300"}`}>
                  {score.toFixed(3)}
                </span>
              </div>
            ))}
            {!drift?.psi_by_feature && <p className="text-slate-500">Insufficient live data yet.</p>}
          </div>
        </section>

        {live && (
          <section className="rounded-xl border border-edge bg-panel p-4 lg:col-span-2">
            <h2 className="mb-3 text-sm font-semibold">Live operations — last {live.window_hours}h</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatCard label="Transactions" value={live.total_transactions.toLocaleString("en-IN")} />
              <StatCard label="Avg latency" value={`${live.avg_latency_ms} ms`} />
              <StatCard
                label="Blocked value"
                value={`₹${Math.round(live.blocked_or_escalated_value_inr).toLocaleString("en-IN")}`}
                accent="text-rose-300"
              />
              <StatCard
                label="In review queue"
                value={`₹${Math.round(live.review_queue_value_inr).toLocaleString("en-IN")}`}
                accent="text-amber-300"
              />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
