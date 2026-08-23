import type { Action } from "@/lib/types";

const STYLES: Record<Action, string> = {
  ALLOW: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  REVIEW: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  BLOCK: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  ESCALATE: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",
};

export default function RiskBadge({ action }: { action: Action }) {
  return (
    <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${STYLES[action] ?? ""}`}>
      {action}
    </span>
  );
}
