"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Coins,
  Lock,
  BookOpen,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  GraduationCap,
} from "lucide-react";
import { fetchProfile, UserProfile } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProfile()
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch(() => {
        // If not logged in, redirect to /login
        router.push("/login");
      });
  }, [router]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="animate-pulse space-y-6">
          <div className="h-28 bg-slate-200 rounded-2xl w-full"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="h-36 bg-slate-200 rounded-2xl"></div>
            <div className="h-36 bg-slate-200 rounded-2xl"></div>
            <div className="h-36 bg-slate-200 rounded-2xl"></div>
          </div>
        </div>
      </div>
    );
  }

  const offeredCount = profile?.offered_skills?.length || 0;
  const desiredCount = profile?.desired_skills?.length || 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-indigo-700 via-indigo-600 to-indigo-800 rounded-3xl p-6 sm:p-8 text-white shadow-xl shadow-indigo-200">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/30 text-indigo-100 text-xs font-semibold backdrop-blur-md">
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              <span>Campus Peer Exchange Node</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Welcome back, {profile?.full_name}!
            </h1>
            <p className="text-indigo-100 text-sm max-w-xl">
              {profile?.department} · Year {profile?.study_year} · Active Peer Member
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/profile"
              className="px-4 py-2.5 bg-white text-indigo-700 font-bold rounded-xl text-sm hover:bg-indigo-50 transition-colors shadow-sm inline-flex items-center gap-1.5"
            >
              <span>Manage Skills</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/wallet"
              className="px-4 py-2.5 bg-indigo-500/40 text-white font-semibold rounded-xl text-sm hover:bg-indigo-500/60 transition-colors backdrop-blur-md inline-flex items-center gap-1.5"
            >
              <span>View Vault</span>
            </Link>
          </div>
        </div>

        {/* Decorative circle glow */}
        <div className="absolute -right-16 -top-16 w-64 h-64 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Available Balance Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Available Credits
            </span>
            <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Coins className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 tabular-nums">
              {(profile?.balance ?? 3).toFixed(2)}
            </span>
            <span className="text-sm font-semibold text-slate-500">hours</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Spendable immediately to book peer mentors
          </p>
        </div>

        {/* Escrow Held Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Escrow Held
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Lock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 tabular-nums">
              0.00
            </span>
            <span className="text-sm font-semibold text-slate-500">credits</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Guaranteed in pending sessions
          </p>
        </div>

        {/* Teaching Skills Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Teaching Skills
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <GraduationCap className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 tabular-nums">
              {offeredCount}
            </span>
            <span className="text-sm font-semibold text-slate-500">offered</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Skills you can exchange for credits
          </p>
        </div>

        {/* Learning Goals Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Learning Goals
            </span>
            <div className="w-9 h-9 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center">
              <BookOpen className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 tabular-nums">
              {desiredCount}
            </span>
            <span className="text-sm font-semibold text-slate-500">goals</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Topics you are currently learning
          </p>
        </div>
      </div>

      {/* Skills Preview & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Skills Quick Preview */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Your Active Skill Catalog</h2>
              <p className="text-xs text-slate-500">Configured in US-02 Skill Profile</p>
            </div>
            <Link
              href="/profile"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              <span>Edit Catalog</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Teaching Preview */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2.5">
                Skills I Teach ({offeredCount})
              </span>
              {offeredCount > 0 ? (
                <div className="space-y-2">
                  {profile?.offered_skills?.slice(0, 3).map((s) => (
                    <div key={s.id} className="flex items-center justify-between bg-white p-2.5 rounded-lg border border-slate-200 text-xs">
                      <span className="font-semibold text-slate-800">{s.name}</span>
                      <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium capitalize">
                        {s.level}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-3 text-center">
                  No teaching skills added yet. Add skills to start earning credits!
                </p>
              )}
            </div>

            {/* Learning Preview */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2.5">
                Skills I Want to Learn ({desiredCount})
              </span>
              {desiredCount > 0 ? (
                <div className="space-y-2">
                  {profile?.desired_skills?.slice(0, 3).map((s) => (
                    <div key={s.id} className="flex items-center justify-between bg-white p-2.5 rounded-lg border border-slate-200 text-xs">
                      <span className="font-semibold text-slate-800">{s.name}</span>
                      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium capitalize">
                        {s.level}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-3 text-center">
                  No learning goals set. Add goals to get matched with campus mentors.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Time Banking Economy Rules */}
        <div className="bg-gradient-to-br from-slate-900 to-indigo-950 text-white rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h3 className="font-bold text-sm tracking-wide uppercase text-indigo-200">
                Time-Banking Rules
              </h3>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              SkillSwap operates on a zero-sum peer time currency. 1 credit equals 1 hour of student knowledge sharing.
            </p>
            <div className="space-y-2.5 text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
                <span>Earn credits by tutoring peers in your strong subjects.</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
                <span>Spend credits to get 1-on-1 help in subjects you want to learn.</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400"></div>
                <span>Zero financial cost; verified campus student network.</span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-800">
            <Link
              href="/wallet"
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center justify-between"
            >
              <span>View Zero-Sum Ledger Audit</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
