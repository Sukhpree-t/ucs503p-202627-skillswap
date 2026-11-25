"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  Clock,
  Coins,
  GraduationCap,
  Star,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  BookOpen,
} from "lucide-react";
import {
  fetchMentorProfile,
  fetchAuthMe,
  MentorPublicProfile,
  UserProfile,
} from "@/lib/api";

export default function MentorProfilePage() {
  const params = useParams();
  const mentorId = params.id as string;

  const [mentor, setMentor] = useState<MentorPublicProfile | null>(null);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mentorId) return;

    Promise.all([
      fetchMentorProfile(mentorId),
      fetchAuthMe().catch(() => null),
    ])
      .then(([m, cur]) => {
        setMentor(m);
        setCurrentUser(cur);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load mentor profile.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [mentorId]);

  const formatSlotDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    } catch {
      return isoString;
    }
  };

  const formatSlotTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoString;
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-slate-200 rounded-lg w-1/4"></div>
          <div className="h-48 bg-slate-200 rounded-3xl"></div>
          <div className="h-64 bg-slate-200 rounded-2xl"></div>
        </div>
      </div>
    );
  }

  if (error || !mentor) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900">Mentor Profile Not Found</h2>
        <p className="text-sm text-slate-600 mt-1 mb-6">
          {error || "The requested peer mentor profile does not exist or has been deactivated."}
        </p>
        <Link
          href="/search"
          className="px-4 py-2.5 bg-indigo-600 text-white font-semibold rounded-xl text-sm hover:bg-indigo-700 transition-colors inline-flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Search</span>
        </Link>
      </div>
    );
  }

  const isOwnProfile = currentUser?.id === mentor.id;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          href="/search"
          className="text-xs text-slate-500 hover:text-indigo-600 font-medium inline-flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Mentors Search</span>
        </Link>
      </div>

      {/* Own Profile Notice */}
      {isOwnProfile && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-2xl flex items-center justify-between text-indigo-900 text-sm">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-600 shrink-0" />
            <span>This is how your public mentor profile appears to learners (US-07).</span>
          </div>
          <Link
            href="/availability"
            className="px-3 py-1.5 bg-indigo-600 text-white font-bold text-xs rounded-xl hover:bg-indigo-700 transition-colors"
          >
            Manage Schedule
          </Link>
        </div>
      )}

      {/* Profile Header Card */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-5">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white font-black text-2xl flex items-center justify-center shadow-lg shadow-indigo-200 shrink-0">
            {mentor.full_name
              .split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("")}
          </div>

          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                {mentor.full_name}
              </h1>
              <span className="px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-bold border border-indigo-100">
                Peer Mentor
              </span>
            </div>

            <p className="text-sm text-slate-600 flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-slate-400" />
              <span>{mentor.department}</span>
              {mentor.study_year && <span>· Year {mentor.study_year}</span>}
            </p>

            <div className="flex items-center gap-3 pt-1 text-xs">
              <span className="flex items-center gap-1 font-bold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200">
                <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                <span>
                  {mentor.mentor_rating_avg > 0 ? mentor.mentor_rating_avg.toFixed(1) : "Unrated"}
                  {mentor.mentor_rating_count > 0 && ` (${mentor.mentor_rating_count} reviews)`}
                </span>
              </span>
              <span className="text-slate-500">
                Verified Campus Student
              </span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div>
          {isOwnProfile ? (
            <Link
              href="/profile"
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold rounded-xl text-xs transition-colors"
            >
              Edit My Profile
            </Link>
          ) : (
            <a
              href="#slots"
              className="px-5 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-sm transition-colors shadow-sm inline-flex items-center gap-2"
            >
              <Calendar className="w-4 h-4" />
              <span>View Open Slots ({mentor.open_slots.length})</span>
            </a>
          )}
        </div>
      </div>

      {/* Bio & Skills */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* About Bio */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
              About This Mentor
            </h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              {mentor.bio || "Peer learner and mentor eager to exchange skills on campus."}
            </p>
          </div>

          <div className="bg-gradient-to-br from-indigo-50 to-emerald-50 rounded-2xl border border-indigo-100 p-6 text-xs text-slate-700 space-y-2">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Escrow Protection Guaranteed</span>
            </div>
            <p className="text-slate-600">
              Booking credits are held safely in escrow and only transferred upon mutual session completion. Auto-refunds apply for no-shows.
            </p>
          </div>
        </div>

        {/* Skills Offered */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-indigo-600" />
              <span>Skills Offered to Teach</span>
            </h3>

            {mentor.offered_skills.length === 0 ? (
              <p className="text-sm text-slate-500 italic">No skills listed yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {mentor.offered_skills.map((skill) => (
                  <div
                    key={skill.id}
                    className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-slate-900 text-sm">{skill.skill_name}</span>
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">
                          {skill.level}
                        </span>
                      </div>
                      {skill.category && (
                        <span className="text-xs text-slate-500 mt-0.5 block">{skill.category}</span>
                      )}
                    </div>
                    <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs font-semibold text-emerald-700">
                      <span>Rate:</span>
                      <span className="flex items-center gap-1">
                        <Coins className="w-3.5 h-3.5" />
                        <span>{skill.hourly_rate_credits || 1} credits / hr</span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Open Availability Slots Section */}
          <div id="slots" className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-indigo-600" />
                <span>Upcoming Availability Slots (US-07 / US-08)</span>
              </h3>
              <span className="text-xs text-slate-500 font-medium">
                {mentor.open_slots.length} open slot{mentor.open_slots.length === 1 ? "" : "s"}
              </span>
            </div>

            {mentor.open_slots.length === 0 ? (
              <div className="text-center py-12 px-4 border-2 border-dashed border-slate-200 rounded-xl">
                <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <h4 className="text-sm font-semibold text-slate-800">No open slots available right now</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  This mentor does not have active open slots on their calendar. Please check back later.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {mentor.open_slots.map((slot) => (
                  <div
                    key={slot.id}
                    className="p-4 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/20 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex flex-col items-center justify-center shrink-0">
                        <Clock className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900 text-sm">
                            {formatSlotDate(slot.start_time)}
                          </span>
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                            Available
                          </span>
                        </div>
                        <div className="text-xs text-slate-600 mt-0.5 flex items-center gap-3">
                          <span>{formatSlotTime(slot.start_time)} – {formatSlotTime(slot.end_time)}</span>
                          <span className="font-bold text-emerald-700 flex items-center gap-1">
                            <Coins className="w-3 h-3" />
                            <span>{slot.rate_credits} credits</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    {!isOwnProfile && (
                      <button
                        onClick={() => {
                          alert(`Slot selection ready! Full escrow lock and session booking will activate in Sprint 3 (US-10). Slot ID: ${slot.id}`);
                        }}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-xs transition-colors self-end sm:self-auto cursor-pointer shadow-sm"
                      >
                        Book Slot ({slot.rate_credits} cr)
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
