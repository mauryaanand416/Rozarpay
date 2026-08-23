"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Live Feed", icon: "◉" },
  { href: "/queue", label: "Review Queue", icon: "⚑" },
  { href: "/audit", label: "Audit Ledger", icon: "⛓" },
  { href: "/metrics", label: "Model Metrics", icon: "📈" },
  { href: "/digest", label: "Risk Digest", icon: "✉" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 w-56 border-r border-edge bg-panel p-4 flex flex-col">
      <div className="mb-8">
        <div className="text-lg font-bold tracking-tight">SentinelPay</div>
        <div className="text-xs text-slate-400">AI Risk Manager</div>
      </div>
      <nav className="flex flex-col gap-1">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                active ? "bg-sky-500/15 text-sky-300" : "text-slate-300 hover:bg-slate-800/60"
              }`}
            >
              <span className="mr-2">{l.icon}</span>
              {l.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto text-[10px] leading-relaxed text-slate-500">
        Razorpay AI Buildathon
        <br />
        Track 02 — AI Risk Manager
      </div>
    </aside>
  );
}
