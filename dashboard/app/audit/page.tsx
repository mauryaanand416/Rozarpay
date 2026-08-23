"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AuditItem } from "@/lib/types";

export default function AuditLedger() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [chain, setChain] = useState<{ valid: boolean; entries?: number; head_hash?: string; reason?: string } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [audit, verify] = await Promise.all([
        api<{ items: AuditItem[] }>("/api/v1/audit?limit=150"),
        api<{ valid: boolean; entries?: number; head_hash?: string; reason?: string }>("/api/v1/audit/verify"),
      ]);
      setItems(audit.items);
      setChain(verify);
      setError(null);
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Audit Ledger</h1>
          <p className="text-xs text-slate-400">
            Tamper-evident hash chain — each entry commits to the previous entry&apos;s hash
          </p>
        </div>
        {chain && (
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              chain.valid
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-rose-500/40 bg-rose-500/10 text-rose-300"
            }`}
          >
            chain {chain.valid ? "valid" : `BROKEN @ seq ${chain.reason}`} · {chain.entries ?? "?"} entries
          </span>
        )}
      </header>

      {chain && !chain.valid && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
          Chain verification failed: {chain.reason}. Entries after the break point may have been tampered with.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>
      )}

      <div className="overflow-x-auto rounded-xl border border-edge bg-panel">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-slate-400">
            <tr>
              <th className="px-4 py-2.5">Seq</th>
              <th className="px-4 py-2.5">Actor</th>
              <th className="px-4 py-2.5">Action</th>
              <th className="px-4 py-2.5">Payload</th>
              <th className="px-4 py-2.5">Hash</th>
              <th className="px-4 py-2.5">Time</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.seq} className="border-b border-edge/50 hover:bg-slate-800/30">
                <td className="px-4 py-2 font-mono">{e.seq}</td>
                <td className="px-4 py-2">{e.actor}</td>
                <td className="px-4 py-2">
                  <span
                    className={`rounded px-1.5 py-0.5 ${
                      e.action_type.includes("block") || e.action_type.includes("escalate")
                        ? "bg-rose-500/15 text-rose-300"
                        : "bg-slate-800 text-slate-300"
                    }`}
                  >
                    {e.action_type}
                  </span>
                </td>
                <td className="max-w-[380px] truncate px-4 py-2 font-mono text-slate-400" title={JSON.stringify(e.payload)}>
                  {JSON.stringify(e.payload)}
                </td>
                <td className="px-4 py-2 font-mono text-sky-300" title={`prev: ${e.prev_hash}`}>
                  {e.entry_hash}…
                </td>
                <td className="px-4 py-2 text-slate-500">{new Date(e.created_at).toLocaleTimeString("en-IN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
