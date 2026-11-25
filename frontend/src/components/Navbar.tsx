"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Coins,
  Lock,
  User,
  LogOut,
  Sparkles,
  Bell,
  CheckCircle2,
} from "lucide-react";
import {
  clearAuthSession,
  fetchAuthMe,
  getStoredUser,
  fetchNotifications,
  UserProfile,
  NotificationItem,
} from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [showNotifs, setShowNotifs] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored) {
      setUser(stored);
    }
    // Refresh user balance & notifications from server
    fetchAuthMe()
      .then((u) => setUser(u))
      .catch(() => {});

    fetchNotifications()
      .then((n) => setNotifications(n))
      .catch(() => {});
  }, [pathname]);

  if (pathname === "/login") return null;

  const handleLogout = () => {
    clearAuthSession();
    setUser(null);
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2.5 group">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-200 group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight block leading-tight">
                SkillSwap
              </span>
              <span className="text-xs text-indigo-600 font-medium tracking-wide">
                Campus Exchange
              </span>
            </div>
          </Link>

          {/* Navigation links */}
          <nav className="hidden md:flex items-center gap-1 pl-4 border-l border-slate-200">
            <Link
              href="/dashboard"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/dashboard" || pathname === "/"
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Dashboard
            </Link>
            <Link
              href="/search"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname.startsWith("/search") || pathname.startsWith("/mentors")
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Find Mentors
            </Link>
            <Link
              href="/availability"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/availability"
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              My Schedule
            </Link>
            <Link
              href="/profile"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/profile"
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Skills & Profile
            </Link>
            <Link
              href="/wallet"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/wallet"
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Ledger Vault
            </Link>
          </nav>
        </div>

        {/* User Balance & Profile Info */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              {/* Balances Pill */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200">
                <div className="flex items-center gap-1.5 text-indigo-700 font-semibold text-xs sm:text-sm">
                  <Coins className="w-4 h-4 text-indigo-600" />
                  <span className="tabular-nums">{(user.balance ?? 3).toFixed(2)} cr</span>
                </div>
                <span className="text-slate-300">|</span>
                <div className="flex items-center gap-1 text-amber-700 text-xs font-medium bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                  <Lock className="w-3 h-3 text-amber-600" />
                  <span>0.00 in escrow</span>
                </div>
              </div>

              {/* US-13: Notifications Popover */}
              <div className="relative">
                <button
                  onClick={() => setShowNotifs(!showNotifs)}
                  title="Notifications"
                  className="p-2 rounded-xl text-slate-500 hover:text-indigo-600 hover:bg-indigo-50/60 transition-colors relative cursor-pointer"
                >
                  <Bell className="w-4 h-4" />
                  {notifications.length > 0 && (
                    <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-indigo-600 ring-2 ring-white"></span>
                  )}
                </button>

                {showNotifs && (
                  <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-200 py-3 z-50">
                    <div className="px-4 pb-2 border-b border-slate-100 flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900">Notifications (US-13)</span>
                      <span className="text-[10px] text-indigo-600 font-medium">Real-Time</span>
                    </div>

                    <div className="max-h-64 overflow-y-auto divide-y divide-slate-50 px-2 py-1">
                      {notifications.length === 0 ? (
                        <div className="text-center py-6 text-xs text-slate-400">
                          No notifications yet
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <div key={n.id} className="p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
                            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                              <span>{n.title}</span>
                            </div>
                            {n.body && (
                              <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">
                                {n.body}
                              </p>
                            )}
                            <span className="text-[10px] text-slate-400 mt-1 block">
                              {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* User Identity */}
              <div className="flex items-center gap-2 pl-2">
                <div className="hidden sm:flex flex-col text-right leading-tight">
                  <span className="text-xs font-semibold text-slate-800">{user.full_name}</span>
                  <span className="text-[11px] text-slate-500 truncate max-w-[140px]">
                    {user.department || "Peer"}
                  </span>
                </div>
                <div className="w-8 h-8 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 font-semibold text-xs overflow-hidden">
                  {user.avatar_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
                  ) : (
                    <User className="w-4 h-4" />
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  title="Sign Out"
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors ml-1"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </>
          ) : (
            <Link
              href="/login"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 shadow-sm transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
