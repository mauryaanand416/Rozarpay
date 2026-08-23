import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "SentinelPay — AI Risk Manager",
  description: "Real-time fraud detection with explainable, gated decisions and a tamper-evident audit trail.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface text-slate-100 antialiased">
        <Sidebar />
        <main className="ml-56 p-6">{children}</main>
      </body>
    </html>
  );
}
