/**
 * SkillSwap API Client
 * Talks to Python FastAPI backend at http://localhost:8000
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface UserProfile {
  id: string;
  campus_email: string;
  full_name: string;
  avatar_url?: string;
  department?: string;
  study_year?: number;
  bio?: string;
  role: string;
  status: string;
  mentor_rating_avg: number;
  mentor_rating_count: number;
  learner_rating_avg: number;
  learner_rating_count: number;
  balance: number;
  offered_skills?: UserSkill[];
  desired_skills?: UserSkill[];
}

export interface UserSkill {
  id: string;
  skill_id: string;
  name: string;
  slug: string;
  category?: string;
  level: "beginner" | "intermediate" | "advanced";
  description?: string;
  hourly_rate_credits?: number;
  embedding_stale?: boolean;
}

export interface AppConfig {
  starter_credits: number;
  campus_domain: string;
  campus_node: string;
}

export async function fetchAppConfig(): Promise<AppConfig> {
  return apiRequest<AppConfig>("/config");
}

export interface SkillCatalogItem {
  id: string;
  name: string;
  slug: string;
  category: string;
}

export interface LedgerTransactionItem {
  transaction_id: string;
  type: string;
  description: string;
  created_at: string;
  direction: "debit" | "credit";
  amount: number;
  delta: number;
}

export interface WalletSummary {
  account_id: string;
  available_balance: number;
  escrow_balance: number;
  total_balance: number;
  history: LedgerTransactionItem[];
}

export interface LedgerAuditResult {
  report_id: string;
  passed: boolean;
  zero_sum_delta: number;
  total_debits: number;
  total_credits: number;
  total_issued: number;
  audited_at: string;
}

// Storage helpers
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("skillswap_token");
}

export function setAuthSession(token: string, user: UserProfile): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("skillswap_token", token);
  localStorage.setItem("skillswap_user", JSON.stringify(user));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("skillswap_token");
  localStorage.removeItem("skillswap_user");
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("skillswap_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// API caller
async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorMsg = `Server error (${res.status})`;
    try {
      const errData = await res.json();
      errorMsg = errData.detail || errData.message || errorMsg;
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return res.json() as Promise<T>;
}

// Auth API (US-01)
export async function campusSSOLogin(params: {
  email: string;
  full_name?: string;
  department?: string;
  study_year?: number;
}): Promise<{ token: string; user: UserProfile }> {
  const data = await apiRequest<{ token: string; user: UserProfile }>("/auth/campus-sso", {
    method: "POST",
    body: JSON.stringify(params),
  });
  setAuthSession(data.token, data.user);
  return data;
}

export async function fetchAuthMe(): Promise<UserProfile> {
  const user = await apiRequest<UserProfile>("/auth/me");
  if (typeof window !== "undefined") {
    localStorage.setItem("skillswap_user", JSON.stringify(user));
  }
  return user;
}

// Profile API (US-02)
export async function fetchProfile(): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me");
}

export async function updateProfileDetails(params: {
  bio?: string;
  department?: string;
  study_year?: number;
}): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}

export async function fetchSkillsCatalog(): Promise<SkillCatalogItem[]> {
  return apiRequest<SkillCatalogItem[]>("/skills");
}

export async function addProfileSkill(params: {
  skill_name: string;
  kind: "offered" | "desired";
  level: "beginner" | "intermediate" | "advanced";
  hourly_rate_credits?: number;
  description?: string;
}): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/skills", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function deleteProfileSkill(userSkillId: string): Promise<UserProfile> {
  return apiRequest<UserProfile>(`/profile/skills/${userSkillId}`, {
    method: "DELETE",
  });
}

// Wallet & Ledger API (US-04)
export async function fetchWalletSummary(): Promise<WalletSummary> {
  return apiRequest<WalletSummary>("/wallet/me");
}

export async function fetchLedgerAudit(): Promise<LedgerAuditResult> {
  return apiRequest<LedgerAuditResult>("/wallet/audit");
}
