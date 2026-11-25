"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Coins,
  RefreshCw,
  Ban,
  WifiOff,
} from "lucide-react";
import { campusSSOLogin, fetchAppConfig } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [department, setDepartment] = useState("Computer Science & Engineering");
  const [studyYear, setStudyYear] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<"general" | "suspended" | "unavailable" | null>(null);
  const [starterCredits, setStarterCredits] = useState<number>(3);

  useEffect(() => {
    fetchAppConfig()
      .then((cfg) => {
        if (cfg?.starter_credits) {
          setStarterCredits(cfg.starter_credits);
        }
      })
      .catch(() => {});
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setErrorType(null);

    if (!email.trim() || !email.includes("@")) {
      setError("Please enter a valid campus email address (e.g. yourname@campus.edu).");
      setErrorType("general");
      return;
    }

    setLoading(true);
    try {
      await campusSSOLogin({
        email: email.trim(),
        full_name: fullName.trim() || undefined,
        department,
        study_year: studyYear,
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to sign in. Please verify your campus credentials.";
      setError(msg);
      if (msg.toLowerCase().includes("suspended")) {
        setErrorType("suspended");
      } else if (msg.toLowerCase().includes("unavailable")) {
        setErrorType("unavailable");
      } else {
        setErrorType("general");
      }
    } finally {
      setLoading(false);
    }
  };

  const selectDemoUser = (userEmail: string, name: string, dept: string, year: number) => {
    setEmail(userEmail);
    setFullName(name);
    setDepartment(dept);
    setStudyYear(year);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Logo and Brand Header */}
        <div className="flex justify-center">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-200">
            <Sparkles className="w-8 h-8" />
          </div>
        </div>
        <h2 className="mt-4 text-center text-3xl font-extrabold text-slate-900 tracking-tight">
          Campus SkillSwap
        </h2>
        <p className="mt-1 text-center text-sm text-slate-600">
          Decentralized Credit-Based Peer Skill Exchange
        </p>

        {/* Starter Credit Callout */}
        <div className="mt-4 mx-4 sm:mx-0 p-3.5 bg-gradient-to-r from-indigo-50 to-emerald-50 rounded-xl border border-indigo-100 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500 text-white flex items-center justify-center shrink-0 shadow-sm">
            <Coins className="w-5 h-5" />
          </div>
          <div className="text-xs text-slate-700">
            <span className="font-semibold text-slate-900 block">First Time Here?</span>
            New campus accounts receive <strong className="text-emerald-700 font-bold">{starterCredits.toFixed(2)} starter time credits</strong> minted automatically!
          </div>
        </div>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl shadow-slate-200/60 sm:rounded-2xl border border-slate-200/80">
          {error && errorType === "suspended" && (
            <div className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-900 text-sm">
              <Ban className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Account Suspended</p>
                <p className="mt-0.5 text-rose-700">{error} — contact your campus administrator to appeal.</p>
              </div>
            </div>
          )}
          {error && errorType === "unavailable" && (
            <div className="mb-5 p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5 text-amber-900 text-sm">
              <WifiOff className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Campus SSO Unavailable</p>
                <p className="mt-0.5 text-amber-700">The campus identity provider is unreachable. Check your campus network or{" "}
                  <button
                    type="button"
                    onClick={() => { setError(null); setErrorType(null); }}
                    className="underline font-semibold hover:text-amber-900"
                  >
                    try again <RefreshCw className="inline w-3.5 h-3.5" />
                  </button>.
                </p>
              </div>
            </div>
          )}
          {error && errorType === "general" && (
            <div className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-800 text-sm">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Campus Email Address
              </label>
              <div className="mt-1.5 relative">
                <input
                  id="email"
                  type="email"
                  required
                  placeholder="student.id@thapar.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 text-slate-900 text-sm outline-none transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            <div>
              <label htmlFor="fullName" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Full Name (Optional for SSO)
              </label>
              <div className="mt-1.5">
                <input
                  id="fullName"
                  type="text"
                  placeholder="e.g. Alex Vance"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 text-slate-900 text-sm outline-none transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Department
                </label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="mt-1.5 w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                >
                  <option value="Computer Science & Engineering">Computer Science</option>
                  <option value="Electronics & Communication">ECE</option>
                  <option value="Mechanical Engineering">Mechanical</option>
                  <option value="Biotechnology">Biotechnology</option>
                  <option value="Mathematics & Computing">Math & Computing</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Study Year
                </label>
                <select
                  value={studyYear}
                  onChange={(e) => setStudyYear(Number(e.target.value))}
                  className="mt-1.5 w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                >
                  <option value={1}>1st Year (Freshman)</option>
                  <option value={2}>2nd Year (Sophomore)</option>
                  <option value={3}>3rd Year (Junior)</option>
                  <option value={4}>4th Year (Senior)</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-4 flex items-center justify-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-all cursor-pointer"
            >
              {loading ? (
                <span>Authenticating with Campus SSO...</span>
              ) : (
                <>
                  <span>Sign in with Campus SSO</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Personas */}
          <div className="mt-6 pt-5 border-t border-slate-200">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5 text-center">
              Or pick a test campus student:
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() =>
                  selectDemoUser(
                    "alex.vance@campus.edu",
                    "Alex Vance",
                    "Computer Science & Engineering",
                    3
                  )
                }
                className="p-2.5 text-left rounded-xl border border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/50 transition-all text-xs"
              >
                <span className="font-bold text-slate-800 block">Alex Vance</span>
                <span className="text-slate-500 text-[11px]">CS &apos;25 (Peer Mentor)</span>
              </button>
              <button
                type="button"
                onClick={() =>
                  selectDemoUser(
                    "maya.patel@campus.edu",
                    "Maya Patel",
                    "Electronics & Communication",
                    2
                  )
                }
                className="p-2.5 text-left rounded-xl border border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/50 transition-all text-xs"
              >
                <span className="font-bold text-slate-800 block">Maya Patel</span>
                <span className="text-slate-500 text-[11px]">ECE &apos;26 (Peer Learner)</span>
              </button>
            </div>
          </div>

          <div className="mt-5 flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Zero-trust double-entry ledger security enabled</span>
          </div>
        </div>
      </div>
    </div>
  );
}
