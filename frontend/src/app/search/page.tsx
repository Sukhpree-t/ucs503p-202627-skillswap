"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Sparkles,
  Star,
  Coins,
  Calendar,
  Filter,
  ArrowRight,
  BookOpen,
  GraduationCap,
  Clock,
  RotateCcw,
} from "lucide-react";
import { searchMentors, MentorSearchResult } from "@/lib/api";

const POPULAR_GOALS = [
  "Build async REST APIs with Python",
  "React & Next.js fullstack development",
  "Data Structures & Algorithm interview prep",
  "Machine Learning & AI fundamentals",
  "System Design & Cloud Architecture",
  "UI/UX Design with Figma",
];

export default function SearchMentorsPage() {
  const [goalQuery, setGoalQuery] = useState("");
  const [maxRate, setMaxRate] = useState<number | undefined>(undefined);
  const [minRating, setMinRating] = useState<number>(0);
  const [results, setResults] = useState<MentorSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [suggestBroader, setSuggestBroader] = useState(false);

  const executeSearch = useCallback(async (queryText: string, rateLimit = maxRate, ratingLimit = minRating) => {
    if (!queryText.trim()) {
      setResults([]);
      setHasSearched(false);
      return;
    }

    setLoading(true);
    setHasSearched(true);
    try {
      const resp = await searchMentors(queryText, rateLimit, ratingLimit);
      setResults(resp.results);
      setSuggestBroader(resp.suggest_broader);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [maxRate, minRating]);

  // Auto-search initially with a broad query to show available mentors
  useEffect(() => {
    executeSearch("Python or React development");
  }, [executeSearch]);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(goalQuery);
  };

  const selectGoalPill = (goal: string) => {
    setGoalQuery(goal);
    executeSearch(goal);
  };

  const formatSlotTime = (isoString?: string) => {
    if (!isoString) return null;
    try {
      const d = new Date(isoString);
      return `${d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} at ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } catch {
      return null;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Search Header Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-indigo-800 via-indigo-700 to-indigo-900 rounded-3xl p-6 sm:p-10 text-white shadow-xl shadow-indigo-200">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/30 text-indigo-100 text-xs font-semibold backdrop-blur-md">
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            <span>Semantic Vector Discovery (US-05)</span>
          </div>

          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">
            Find Peer Mentors by Your Learning Goal
          </h1>
          <p className="text-indigo-100 text-sm sm:text-base leading-relaxed">
            Type what you want to learn in natural language. Our semantic vector engine matches you with qualified campus peers ready to exchange knowledge.
          </p>

          {/* Search Bar */}
          <form onSubmit={handleFormSubmit} className="pt-2">
            <div className="relative flex items-center bg-white rounded-2xl shadow-lg shadow-indigo-950/20 p-1.5 sm:p-2 border border-white/20">
              <Search className="w-5 h-5 text-slate-400 ml-3 shrink-0" />
              <input
                type="text"
                placeholder="e.g. Master Next.js App Router and TypeScript, or learn dynamic programming..."
                value={goalQuery}
                onChange={(e) => setGoalQuery(e.target.value)}
                className="w-full px-3 py-2 text-slate-900 text-sm outline-none placeholder:text-slate-400 bg-transparent"
              />
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-sm transition-colors shrink-0 cursor-pointer shadow-sm"
              >
                {loading ? "Matching..." : "Search Mentors"}
              </button>
            </div>
          </form>

          {/* Quick Learning Goal Topic Pills */}
          <div className="pt-2 flex flex-wrap items-center gap-2">
            <span className="text-xs text-indigo-200 font-medium">Try asking for:</span>
            {POPULAR_GOALS.map((goal) => (
              <button
                key={goal}
                type="button"
                onClick={() => selectGoalPill(goal)}
                className="px-2.5 py-1 rounded-lg bg-indigo-600/40 hover:bg-indigo-600/70 text-indigo-100 text-xs font-medium border border-indigo-400/20 backdrop-blur-sm transition-all"
              >
                {goal}
              </button>
            ))}
          </div>
        </div>

        {/* Decorative circle glow */}
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4 text-xs font-medium">
        <div className="flex items-center gap-2 text-slate-700">
          <Filter className="w-4 h-4 text-indigo-600" />
          <span className="font-bold">Filters:</span>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Max Rate Filter */}
          <div className="flex items-center gap-2">
            <label className="text-slate-600">Max Credit Rate:</label>
            <select
              value={maxRate ?? ""}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : undefined;
                setMaxRate(val);
                executeSearch(goalQuery || "learning", val, minRating);
              }}
              className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-slate-800 bg-white outline-none focus:ring-2 focus:ring-indigo-600"
            >
              <option value="">Any Rate</option>
              <option value="1">1 credit/hr max</option>
              <option value="2">2 credits/hr max</option>
              <option value="3">3 credits/hr max</option>
              <option value="5">5 credits/hr max</option>
            </select>
          </div>

          {/* Minimum Rating Filter */}
          <div className="flex items-center gap-2">
            <label className="text-slate-600">Min Mentor Rating:</label>
            <select
              value={minRating}
              onChange={(e) => {
                const val = Number(e.target.value);
                setMinRating(val);
                executeSearch(goalQuery || "learning", maxRate, val);
              }}
              className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-slate-800 bg-white outline-none focus:ring-2 focus:ring-indigo-600"
            >
              <option value="0">Any Rating</option>
              <option value="3">3.0+ Stars</option>
              <option value="4">4.0+ Stars</option>
              <option value="4.5">4.5+ Stars</option>
            </select>
          </div>

          {(maxRate !== undefined || minRating > 0) && (
            <button
              type="button"
              onClick={() => {
                setMaxRate(undefined);
                setMinRating(0);
                executeSearch(goalQuery || "learning", undefined, 0);
              }}
              className="text-indigo-600 hover:text-indigo-800 flex items-center gap-1 font-semibold"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Results Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-900">
            {hasSearched ? `Matching Mentors (${results.length})` : "Featured Mentors"}
          </h2>
          {results.length > 0 && (
            <span className="text-xs text-slate-500">
              Ranked by semantic goal relevance score
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse bg-white p-6 rounded-2xl border border-slate-200 h-64">
                <div className="h-10 bg-slate-200 rounded-lg w-2/3 mb-4"></div>
                <div className="h-4 bg-slate-200 rounded w-full mb-2"></div>
                <div className="h-4 bg-slate-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        ) : results.length === 0 ? (
          <div className="text-center py-16 px-4 bg-white border border-slate-200 rounded-3xl shadow-sm">
            <BookOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-900">No mentors found matching this exact query</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              {suggestBroader
                ? "Try broadening your query keywords or adjusting the rate and rating filters."
                : "Try searching with general concepts like 'Python', 'Algorithms', or 'Figma design'."}
            </p>
            <div className="mt-5 flex justify-center gap-2">
              <button
                onClick={() => selectGoalPill("Python & Backend")}
                className="px-3 py-1.5 bg-indigo-50 text-indigo-700 font-semibold text-xs rounded-xl hover:bg-indigo-100 transition-colors"
              >
                Explore Python Mentors
              </button>
              <button
                onClick={() => selectGoalPill("React & Frontend")}
                className="px-3 py-1.5 bg-indigo-50 text-indigo-700 font-semibold text-xs rounded-xl hover:bg-indigo-100 transition-colors"
              >
                Explore React Mentors
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {results.map((mentor) => (
              <div
                key={mentor.mentor_id}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all p-6 flex flex-col justify-between"
              >
                <div className="space-y-4">
                  {/* Top: Avatar, Name, Match Pill */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-extrabold flex items-center justify-center text-base shadow-sm">
                        {mentor.full_name
                          .split(" ")
                          .map((n) => n[0])
                          .slice(0, 2)
                          .join("")}
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-900 text-base leading-tight">
                          {mentor.full_name}
                        </h3>
                        <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                          <GraduationCap className="w-3.5 h-3.5 text-slate-400" />
                          <span>{mentor.department}</span>
                        </p>
                      </div>
                    </div>

                    <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-bold shrink-0">
                      {mentor.match_score}% Match
                    </span>
                  </div>

                  {/* Bio */}
                  {mentor.bio && (
                    <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                      {mentor.bio}
                    </p>
                  )}

                  {/* Skill Badge & Rate */}
                  <div className="p-3 bg-slate-50 rounded-xl space-y-2 border border-slate-100">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Matched Skill:</span>
                      <span className="font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md">
                        {mentor.matched_skill}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Rate:</span>
                      <span className="font-bold text-emerald-700 flex items-center gap-1">
                        <Coins className="w-3.5 h-3.5" />
                        <span>{mentor.rate_credits} credits / hour</span>
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Rating:</span>
                      <span className="flex items-center gap-1 font-semibold text-amber-700">
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                        <span>
                          {mentor.rating > 0 ? mentor.rating.toFixed(1) : "New"}
                          {mentor.rating_count > 0 && ` (${mentor.rating_count})`}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Next Available Slot Preview */}
                  {mentor.next_slot ? (
                    <div className="text-xs text-slate-600 flex items-center gap-1.5 bg-emerald-50/60 border border-emerald-100 p-2.5 rounded-xl">
                      <Clock className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>Next slot: <strong>{formatSlotTime(mentor.next_slot.start_time)}</strong></span>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400 flex items-center gap-1.5 p-2.5 bg-slate-50 rounded-xl">
                      <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>No upcoming slots scheduled</span>
                    </div>
                  )}
                </div>

                {/* Card Action Link */}
                <div className="pt-5 mt-4 border-t border-slate-100">
                  <Link
                    href={`/mentors/${mentor.mentor_id}`}
                    className="w-full py-2.5 px-4 bg-indigo-50 hover:bg-indigo-600 hover:text-white text-indigo-700 font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5 group cursor-pointer"
                  >
                    <span>View Profile & Slots (US-07)</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
