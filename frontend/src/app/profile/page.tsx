"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  User,
  GraduationCap,
  BookOpen,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  Save,
  Coins,
} from "lucide-react";
import {
  fetchProfile,
  updateProfileDetails,
  addProfileSkill,
  deleteProfileSkill,
  UserProfile,
} from "@/lib/api";

const PRESET_SKILLS = [
  "Python & Backend",
  "Data Structures & Algorithms",
  "React & Frontend",
  "Machine Learning & AI",
  "System Design",
  "UI/UX Design & Figma",
  "SQL & Database Engineering",
  "Cloud & DevOps",
  "Computer Networks",
  "Operating Systems",
];

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatingProfile, setUpdatingProfile] = useState(false);
  const [addingSkill, setAddingSkill] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Profile editable fields
  const [bio, setBio] = useState("");
  const [department, setDepartment] = useState("");
  const [studyYear, setStudyYear] = useState(3);

  // New Skill form fields
  const [showAddModal, setShowAddModal] = useState(false);
  const [skillName, setSkillName] = useState("");
  const [skillKind, setSkillKind] = useState<"offered" | "desired">("offered");
  const [skillLevel, setSkillLevel] = useState<"beginner" | "intermediate" | "advanced">("intermediate");
  const [hourlyRate, setHourlyRate] = useState(1);
  const [skillDesc, setSkillDesc] = useState("");
  const [skillFormError, setSkillFormError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const data = await fetchProfile();
      setProfile(data);
      setBio(data.bio || "");
      setDepartment(data.department || "Computer Science & Engineering");
      setStudyYear(data.study_year || 3);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpdatingProfile(true);
    setStatusMessage(null);
    try {
      const updated = await updateProfileDetails({
        bio: bio.trim(),
        department: department.trim(),
        study_year: Number(studyYear),
      });
      setProfile(updated);
      setStatusMessage({ type: "success", text: "Profile details updated successfully." });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile.";
      setStatusMessage({ type: "error", text: msg });
    } finally {
      setUpdatingProfile(false);
    }
  };

  const handleAddSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    setSkillFormError(null);

    if (!skillName.trim()) {
      setSkillFormError("Please enter or select a skill name.");
      return;
    }

    setAddingSkill(true);
    try {
      const updated = await addProfileSkill({
        skill_name: skillName.trim(),
        kind: skillKind,
        level: skillLevel,
        hourly_rate_credits: skillKind === "offered" ? hourlyRate : undefined,
        description: skillDesc.trim() || undefined,
      });
      setProfile(updated);
      setShowAddModal(false);
      setSkillName("");
      setSkillDesc("");
      setStatusMessage({
        type: "success",
        text: `Skill "${skillName}" added to ${skillKind === "offered" ? "teaching" : "learning"} list.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save skill.";
      setSkillFormError(msg);
    } finally {
      setAddingSkill(false);
    }
  };

  const handleDeleteSkill = async (userSkillId: string, skillName: string) => {
    try {
      const updated = await deleteProfileSkill(userSkillId);
      setProfile(updated);
      setStatusMessage({ type: "success", text: `Removed "${skillName}" from profile.` });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove skill.";
      setStatusMessage({ type: "error", text: msg });
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12 animate-pulse space-y-6">
        <div className="h-44 bg-slate-200 rounded-2xl w-full"></div>
        <div className="h-64 bg-slate-200 rounded-2xl w-full"></div>
      </div>
    );
  }

  const offered = profile?.offered_skills || [];
  const desired = profile?.desired_skills || [];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Skill Profile & Academic Identity
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage your peer teaching catalog, learning goals, and campus credentials
          </p>
        </div>
        <button
          onClick={() => {
            setSkillFormError(null);
            setShowAddModal(true);
          }}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-sm transition-colors text-sm cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add Skill</span>
        </button>
      </div>

      {/* Global Status Message */}
      {statusMessage && (
        <div
          className={`p-4 rounded-xl flex items-center justify-between gap-3 text-sm ${
            statusMessage.type === "success"
              ? "bg-emerald-50 border border-emerald-200 text-emerald-800"
              : "bg-rose-50 border border-rose-200 text-rose-800"
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.type === "success" ? (
              <Check className="w-5 h-5 text-emerald-600" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-xs font-semibold opacity-70 hover:opacity-100"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Profile Overview Card & Edit Form */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-8">
        <form onSubmit={handleUpdateProfile} className="space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 pb-6 border-b border-slate-100">
            <div className="w-16 h-16 rounded-2xl bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 font-extrabold text-2xl overflow-hidden shrink-0 shadow-sm">
              {profile?.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={profile.avatar_url} alt={profile.full_name} className="w-full h-full object-cover" />
              ) : (
                <User className="w-8 h-8" />
              )}
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-slate-900">{profile?.full_name}</h2>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-indigo-600">{profile?.campus_email}</span>
                <span>•</span>
                <span className="bg-slate-100 px-2.5 py-0.5 rounded-full text-slate-700 font-semibold">
                  {profile?.role?.toUpperCase()}
                </span>
                <span>•</span>
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  <Coins className="w-3.5 h-3.5" /> {(profile?.balance ?? 3).toFixed(2)} Credits Available
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Academic Department
              </label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="e.g. Computer Science & Engineering"
                className="mt-1.5 w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Year of Study (1 - 6)
              </label>
              <select
                value={studyYear}
                onChange={(e) => setStudyYear(Number(e.target.value))}
                className="mt-1.5 w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
              >
                <option value={1}>1st Year (Freshman)</option>
                <option value={2}>2nd Year (Sophomore)</option>
                <option value={3}>3rd Year (Junior)</option>
                <option value={4}>4th Year (Senior)</option>
                <option value={5}>5th Year (Dual Degree / Masters)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Bio & Peer Introduction
            </label>
            <textarea
              rows={3}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Tell other students what you're passionate about and how you like to collaborate..."
              className="mt-1.5 w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none resize-none"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={updatingProfile}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 cursor-pointer"
            >
              <Save className="w-4 h-4" />
              <span>{updatingProfile ? "Saving Details..." : "Save Profile Details"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Dual Skills Sections: Teaching vs Learning */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Skills I Can Teach */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Skills I Can Teach</h3>
                <p className="text-[11px] text-slate-500">Mentoring catalog (Earn credits)</p>
              </div>
            </div>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
              {offered.length}
            </span>
          </div>

          {offered.length === 0 ? (
            <div className="p-8 text-center border-2 border-dashed border-slate-200 rounded-xl space-y-2">
              <p className="text-xs text-slate-500 font-medium">No teaching skills listed yet.</p>
              <p className="text-[11px] text-slate-400">
                Listing skills you can teach allows learners to book you and earn you credits.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSkillKind("offered");
                  setShowAddModal(true);
                }}
                className="mt-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              >
                + Add your first teaching skill
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {offered.map((skill) => (
                <div
                  key={skill.id}
                  className="p-3.5 rounded-xl border border-slate-200/90 hover:border-indigo-300 hover:bg-slate-50/50 transition-all flex items-start justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">{skill.name}</span>
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          skill.level === "advanced"
                            ? "bg-purple-50 text-purple-700 border border-purple-200"
                            : skill.level === "intermediate"
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        }`}
                      >
                        {skill.level}
                      </span>
                    </div>
                    {skill.description && (
                      <p className="text-xs text-slate-600">{skill.description}</p>
                    )}
                    <div className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
                      <Coins className="w-3.5 h-3.5 text-indigo-600" />
                      <span>{skill.hourly_rate_credits || 1} credit / hour</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteSkill(skill.id, skill.name)}
                    title="Remove Skill"
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Skills I Want to Learn */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Skills I Want to Learn</h3>
                <p className="text-[11px] text-slate-500">Learning goals & matching (Spend credits)</p>
              </div>
            </div>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
              {desired.length}
            </span>
          </div>

          {desired.length === 0 ? (
            <div className="p-8 text-center border-2 border-dashed border-slate-200 rounded-xl space-y-2">
              <p className="text-xs text-slate-500 font-medium">No learning goals added yet.</p>
              <p className="text-[11px] text-slate-400">
                Share what topics you want to learn to get matched with skilled classmates.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSkillKind("desired");
                  setShowAddModal(true);
                }}
                className="mt-2 text-xs font-semibold text-emerald-600 hover:text-emerald-800"
              >
                + Add your first learning goal
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {desired.map((skill) => (
                <div
                  key={skill.id}
                  className="p-3.5 rounded-xl border border-slate-200/90 hover:border-emerald-300 hover:bg-slate-50/50 transition-all flex items-start justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">{skill.name}</span>
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {skill.level} Target
                      </span>
                    </div>
                    {skill.description && (
                      <p className="text-xs text-slate-600">{skill.description}</p>
                    )}
                  </div>
                  <button
                    onClick={() => handleDeleteSkill(skill.id, skill.name)}
                    title="Remove Skill"
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Skill Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-lg text-slate-900">Add Skill to Profile</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold cursor-pointer"
              >
                ✕
              </button>
            </div>

            {skillFormError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-800 text-xs">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{skillFormError}</span>
              </div>
            )}

            <form onSubmit={handleAddSkill} className="space-y-4">
              {/* Kind Toggle (Teach vs Learn) */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Category Role
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSkillKind("offered")}
                    className={`p-2.5 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                      skillKind === "offered"
                        ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <GraduationCap className="w-4 h-4" />
                    <span>Skill I Can Teach</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSkillKind("desired")}
                    className={`p-2.5 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                      skillKind === "desired"
                        ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <BookOpen className="w-4 h-4" />
                    <span>Skill I Want to Learn</span>
                  </button>
                </div>
              </div>

              {/* Skill Name Input + Presets */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Skill Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Python & FastAPI, Linear Algebra, Figma"
                  value={skillName}
                  onChange={(e) => setSkillName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                />
                {/* Preset suggestions */}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {PRESET_SKILLS.slice(0, 5).map((preset) => (
                    <button
                      type="button"
                      key={preset}
                      onClick={() => setSkillName(preset)}
                      className="px-2 py-1 rounded-md bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-600 text-[11px] font-medium transition-colors"
                    >
                      + {preset}
                    </button>
                  ))}
                </div>
              </div>

              {/* Proficiency Level */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Proficiency Level
                  </label>
                  <select
                    value={skillLevel}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                      setSkillLevel(e.target.value as "beginner" | "intermediate" | "advanced")
                    }
                    className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                  >
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>

                {skillKind === "offered" ? (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Hourly Rate (Credits)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={hourlyRate}
                      onChange={(e) => setHourlyRate(Number(e.target.value))}
                      className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Standard Cost
                    </label>
                    <div className="px-3 py-2.5 rounded-lg bg-slate-100 text-slate-500 text-sm font-medium">
                      Market Rate (1-3 cr)
                    </div>
                  </div>
                )}
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Optional Details or Focus Area
                </label>
                <input
                  type="text"
                  placeholder="e.g. Can explain Leetcode medium topics or project reviews"
                  value={skillDesc}
                  onChange={(e) => setSkillDesc(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-indigo-600 outline-none"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingSkill}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {addingSkill ? "Adding..." : "Save to Profile"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
