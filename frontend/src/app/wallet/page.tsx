"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Coins,
  Lock,
  ArrowUpRight,
  ArrowDownLeft,
  ShieldCheck,
  RefreshCw,
  Clock,
  FileText,
} from "lucide-react";
import { fetchWalletSummary, fetchLedgerAudit, WalletSummary, LedgerAuditResult } from "@/lib/api";

export default function WalletPage() {
  const router = useRouter();
  const [wallet, setWallet] = useState<WalletSummary | null>(null);
  const [audit, setAudit] = useState<LedgerAuditResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");

  const loadWalletData = useCallback(async () => {
    try {
      const summary = await fetchWalletSummary();
      setWallet(summary);
      const auditResult = await fetchLedgerAudit();
      setAudit(auditResult);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadWalletData();
  }, [loadWalletData]);

  const handleRunAudit = async () => {
    setAuditing(true);
    try {
      const auditResult = await fetchLedgerAudit();
      setAudit(auditResult);
    } catch (err) {
      console.error(err);
    } finally {
      setAuditing(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-12 animate-pulse space-y-6">
        <div className="h-44 bg-slate-200 rounded-2xl w-full"></div>
        <div className="h-80 bg-slate-200 rounded-2xl w-full"></div>
      </div>
    );
  }

  const history = wallet?.history || [];
  const filteredHistory = filterType === "all" ? history : history.filter((h) => h.type === filterType);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full">
              UCS503 Time Vault
            </span>
            <span className="text-xs text-slate-400">·</span>
            <span className="text-xs text-slate-500 font-mono truncate max-w-xs">
              Account #{wallet?.account_id?.slice(0, 8)}...
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mt-1">
            Time Credit Wallet & Ledger Vault
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Double-entry zero-trust ledger holding peer credits and escrow commitments
          </p>
        </div>

        {/* Live Zero-Sum Audit Badge & Trigger */}
        <div className="flex items-center gap-2">
          <div
            className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 ${
              audit?.passed
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-rose-50 border-rose-200 text-rose-800"
            }`}
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Zero-Sum Invariant: {audit?.passed ? "Verified (Sum = 0)" : "Unbalanced"}</span>
          </div>
          <button
            onClick={handleRunAudit}
            disabled={auditing}
            title="Run Live Ledger Audit"
            className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-sm transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${auditing ? "animate-spin text-indigo-600" : ""}`} />
          </button>
        </div>
      </div>

      {/* Balance Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Available Balance */}
        <div className="bg-gradient-to-br from-indigo-600 to-indigo-800 text-white rounded-3xl p-6 sm:p-7 shadow-lg shadow-indigo-100 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-200">
              Available to Spend
            </span>
            <div className="w-9 h-9 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center">
              <Coins className="w-5 h-5 text-amber-300" />
            </div>
          </div>
          <div className="my-5">
            <div className="flex items-baseline gap-2">
              <span className="text-4xl sm:text-5xl font-black tabular-nums tracking-tight">
                {(wallet?.available_balance ?? 3).toFixed(2)}
              </span>
              <span className="text-base font-semibold text-indigo-200">credits</span>
            </div>
            <p className="mt-1 text-xs text-indigo-100">
              Equals {(wallet?.available_balance ?? 3).toFixed(1)} hours of 1-on-1 tutoring sessions
            </p>
          </div>
          <div className="pt-3 border-t border-indigo-500/40 text-[11px] text-indigo-200 flex items-center justify-between">
            <span>Direct DB Account Query</span>
            <span className="font-semibold text-emerald-300">Active</span>
          </div>
        </div>

        {/* Locked in Escrow */}
        <div className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-7 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Escrow Locked
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Lock className="w-5 h-5" />
            </div>
          </div>
          <div className="my-5">
            <div className="flex items-baseline gap-2">
              <span className="text-4xl sm:text-5xl font-black text-slate-900 tabular-nums tracking-tight">
                {(wallet?.escrow_balance ?? 0).toFixed(2)}
              </span>
              <span className="text-base font-semibold text-slate-500">credits</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Held safely by the system until mutual session sign-off
            </p>
          </div>
          <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Protected against no-shows</span>
            <span className="font-semibold text-slate-700">Vault Safe</span>
          </div>
        </div>

        {/* Ledger Solvency & Mint Info */}
        <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-7 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Ledger Metrics
            </span>
            <div className="w-9 h-9 rounded-xl bg-slate-800 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="my-4 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Total System Minted:</span>
              <span className="font-bold text-white tabular-nums">{audit?.total_issued ?? 3} credits</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Zero-Sum Balance Delta:</span>
              <span className="font-bold text-emerald-400 tabular-nums">
                {audit?.zero_sum_delta === 0 ? "0 (Balanced)" : `${audit?.zero_sum_delta}`}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Total Balanced Entries:</span>
              <span className="font-bold text-white tabular-nums">
                {audit?.total_debits ?? 3} Dr / {audit?.total_credits ?? 3} Cr
              </span>
            </div>
          </div>
          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-400">
            Rule #5 Enforced: Client never computes balance.
          </div>
        </div>
      </div>

      {/* Transaction History Section */}
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Double-Entry Transaction History</h2>
            <p className="text-xs text-slate-500">Immutable audit log arranged newest first (US-04)</p>
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl text-xs font-semibold text-slate-600">
            <button
              onClick={() => setFilterType("all")}
              className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                filterType === "all" ? "bg-white text-indigo-700 shadow-sm" : "hover:text-slate-900"
              }`}
            >
              All Records
            </button>
            <button
              onClick={() => setFilterType("starter_grant")}
              className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                filterType === "starter_grant" ? "bg-white text-indigo-700 shadow-sm" : "hover:text-slate-900"
              }`}
            >
              Grants
            </button>
            <button
              onClick={() => setFilterType("settlement")}
              className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                filterType === "settlement" ? "bg-white text-indigo-700 shadow-sm" : "hover:text-slate-900"
              }`}
            >
              Settlements
            </button>
          </div>
        </div>

        {/* History Table */}
        {filteredHistory.length === 0 ? (
          <div className="py-12 text-center border-2 border-dashed border-slate-200 rounded-2xl space-y-2">
            <FileText className="w-8 h-8 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-600">No transactions recorded under this filter.</p>
            <p className="text-xs text-slate-400">New bookings and completed sessions will appear here.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
                  <th className="pb-3 pl-2">Type & Description</th>
                  <th className="pb-3">Transaction ID</th>
                  <th className="pb-3">Timestamp</th>
                  <th className="pb-3 text-right pr-4">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredHistory.map((tx) => {
                  const isCredit = tx.direction === "credit";
                  return (
                    <tr key={`${tx.transaction_id}-${tx.direction}`} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 pl-2">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                              isCredit ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600"
                            }`}
                          >
                            {isCredit ? <ArrowDownLeft className="w-4 h-4" /> : <ArrowUpRight className="w-4 h-4" />}
                          </div>
                          <div>
                            <span className="font-bold text-slate-900 block text-sm">{tx.description}</span>
                            <span className="text-[11px] font-mono text-slate-400 uppercase">
                              {tx.type.replace("_", " ")}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 font-mono text-slate-500 truncate max-w-[120px]">
                        {tx.transaction_id.slice(0, 12)}...
                      </td>
                      <td className="py-4 text-slate-500">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>{new Date(tx.created_at).toLocaleString()}</span>
                        </div>
                      </td>
                      <td className="py-4 text-right pr-4 font-bold tabular-nums text-sm">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-lg ${
                            isCredit
                              ? "bg-emerald-50 text-emerald-700 font-extrabold"
                              : "bg-rose-50 text-rose-700 font-extrabold"
                          }`}
                        >
                          {isCredit ? "+" : "-"}
                          {tx.amount.toFixed(2)} cr
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
