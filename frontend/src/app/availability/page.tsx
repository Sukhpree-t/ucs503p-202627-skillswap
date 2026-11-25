"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  Clock,
  Coins,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import {
  fetchAuthMe,
  fetchMySlots,
  createAvailabilitySlot,
  deleteAvailabilitySlot,
  AvailabilitySlot,
  UserProfile,
} from "@/lib/api";

export default function AvailabilityPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form states
  const [slotDate, setSlotDate] = useState<string>(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split("T")[0];
  });
  const [startTime, setStartTime] = useState<string>("14:00");
  const [endTime, setEndTime] = useState<string>("15:00");
  const [rateCredits, setRateCredits] = useState<number>(1);
  const [selectedSkillId, setSelectedSkillId] = useState<string>("");

  useEffect(() => {
    Promise.all([fetchAuthMe(), fetchMySlots()])
      .then(([prof, slotList]) => {
        setProfile(prof);
        setSlots(slotList);
        if (prof?.offered_skills && prof.offered_skills.length > 0) {
          setSelectedSkillId(prof.offered_skills[0].skill_id || prof.offered_skills[0].id);
          if (prof.offered_skills[0].hourly_rate_credits) {
            setRateCredits(prof.offered_skills[0].hourly_rate_credits);
          }
        }
      })
      .catch(() => {
        router.push("/login");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [router]);

  const handleCreateSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!slotDate || !startTime || !endTime) {
      setError("Please specify the date, start time, and end time.");
      return;
    }

    const startDateTime = new Date(`${slotDate}T${startTime}:00Z`);
    const endDateTime = new Date(`${slotDate}T${endTime}:00Z`);

    if (endDateTime <= startDateTime) {
      setError("End time must be strictly after start time.");
      return;
    }

    if (startDateTime.getTime() < Date.now()) {
      setError("Cannot create availability slots in the past.");
      return;
    }

    setSubmitting(true);
    try {
      const newSlot = await createAvailabilitySlot({
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        rate_credits: rateCredits,
        skill_id: selectedSkillId || undefined,
      });
      setSlots((prev) => [...prev, newSlot].sort((a, b) => a.start_time.localeCompare(b.start_time)));
      setSuccess("Availability slot published successfully! Learners can now discover and book it.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create slot. Please check for overlap conflicts.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelSlot = async (slotId: string) => {
    if (!confirm("Are you sure you want to cancel this availability slot?")) return;
    setError(null);
    setSuccess(null);
    try {
      await deleteAvailabilitySlot(slotId);
      setSlots((prev) =>
        prev.map((s) => (s.id === slotId ? { ...s, status: "cancelled" } : s))
      );
      setSuccess("Slot cancelled successfully.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to cancel slot.");
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

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="animate-pulse space-y-6">
          <div className="h-10 bg-slate-200 rounded-lg w-1/3"></div>
          <div className="h-64 bg-slate-200 rounded-2xl"></div>
        </div>
      </div>
    );
  }

  const activeSlots = slots.filter((s) => s.status !== "cancelled");
  const pastSlots = slots.filter((s) => s.status === "cancelled");

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href="/dashboard"
              className="text-xs text-slate-500 hover:text-indigo-600 inline-flex items-center gap-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Dashboard</span>
            </Link>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Calendar className="w-8 h-8 text-indigo-600" />
            <span>Mentor Availability & Rate Publishing</span>
          </h1>
          <p className="text-slate-600 text-sm mt-1">
            Publish your open time slots and hourly credit rate so peer learners can discover and book sessions (US-08).
          </p>
        </div>

        <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-emerald-50 text-emerald-800 text-xs font-semibold border border-emerald-200 self-start sm:self-auto">
          <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
          <span>{activeSlots.length} Active Slots Live</span>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-3 text-emerald-800 text-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <span>{success}</span>
        </div>
      )}

      {/* Main Grid: Form on left, Slots list on right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Slot Publishing Form */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sticky top-24">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
              <Plus className="w-5 h-5 text-indigo-600" />
              <span>Publish New Slot</span>
            </h2>

            <form onSubmit={handleCreateSlot} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Slot Date
                </label>
                <input
                  type="date"
                  required
                  min={new Date().toISOString().split("T")[0]}
                  value={slotDate}
                  onChange={(e) => setSlotDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-slate-900 focus:ring-2 focus:ring-indigo-600 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Start Time
                  </label>
                  <input
                    type="time"
                    required
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-slate-900 focus:ring-2 focus:ring-indigo-600 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    End Time
                  </label>
                  <input
                    type="time"
                    required
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-slate-900 focus:ring-2 focus:ring-indigo-600 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Credit Rate per Hour
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min={1}
                    max={10}
                    required
                    value={rateCredits}
                    onChange={(e) => setRateCredits(Number(e.target.value))}
                    className="w-full px-3 py-2 pl-9 rounded-lg border border-slate-300 text-slate-900 focus:ring-2 focus:ring-indigo-600 outline-none"
                  />
                  <Coins className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Standard rate is 1 to 3 time credits/hr.</p>
              </div>

              {profile?.offered_skills && profile.offered_skills.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Offered Skill Focus
                  </label>
                  <select
                    value={selectedSkillId}
                    onChange={(e) => setSelectedSkillId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-slate-900 focus:ring-2 focus:ring-indigo-600 outline-none"
                  >
                    {profile.offered_skills.map((sk) => (
                      <option key={sk.id} value={sk.skill_id || sk.id}>
                        {sk.name} ({sk.level})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full mt-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-sm text-sm disabled:opacity-50 transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                {submitting ? (
                  <span>Publishing...</span>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    <span>Publish Availability Slot</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Published Slots List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center justify-between">
              <span>Your Scheduled Availability</span>
              <span className="text-xs text-slate-500 font-normal">
                {activeSlots.length} active slot{activeSlots.length === 1 ? "" : "s"}
              </span>
            </h2>

            {activeSlots.length === 0 ? (
              <div className="text-center py-12 px-4 border-2 border-dashed border-slate-200 rounded-xl">
                <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <h3 className="text-sm font-semibold text-slate-800">No active availability slots</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Publish your upcoming free hours using the form on the left. Learners will be able to search and book them.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeSlots.map((slot) => (
                  <div
                    key={slot.id}
                    className="p-4 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/20 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-700 flex flex-col items-center justify-center shrink-0">
                        <Calendar className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900 text-sm">
                            {formatSlotDate(slot.start_time)}
                          </span>
                          <span
                            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                              slot.status === "open"
                                ? "bg-emerald-100 text-emerald-800"
                                : slot.status === "booked"
                                ? "bg-indigo-100 text-indigo-800"
                                : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {slot.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-slate-600 mt-1">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            {formatSlotTime(slot.start_time)} – {formatSlotTime(slot.end_time)}
                          </span>
                          <span className="flex items-center gap-1 font-semibold text-emerald-700">
                            <Coins className="w-3.5 h-3.5 text-emerald-600" />
                            {slot.rate_credits} credit{slot.rate_credits === 1 ? "" : "s"}/hr
                          </span>
                          {slot.skill_name && (
                            <span className="text-slate-500">· {slot.skill_name}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {slot.status === "open" && (
                      <button
                        onClick={() => handleCancelSlot(slot.id)}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors self-end sm:self-auto cursor-pointer"
                        title="Cancel Slot"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {pastSlots.length > 0 && (
            <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                Cancelled / Inactive Slots
              </h3>
              <div className="space-y-2 opacity-60">
                {pastSlots.map((slot) => (
                  <div
                    key={slot.id}
                    className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between text-xs"
                  >
                    <span>{formatSlotDate(slot.start_time)} ({formatSlotTime(slot.start_time)} – {formatSlotTime(slot.end_time)})</span>
                    <span className="text-slate-500 italic">Cancelled</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
