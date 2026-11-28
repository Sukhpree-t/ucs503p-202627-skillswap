"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import DailyIframe, { DailyCall } from "@daily-co/daily-js";
import {
  Video,
  CheckCircle,
  AlertCircle,
  Clock,
  Shield,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import {
  joinVideoSession,
  sendSessionHeartbeat,
  signOffBooking,
  SignOffResponse,
} from "@/lib/api";
import { formatSessionErrorMessage, SessionErrorInfo } from "@/lib/sessionErrors";

export default function SessionRoomPage() {
  const params = useParams();
  const bookingId = params.id as string;

  const containerRef = useRef<HTMLDivElement>(null);
  const callFrameRef = useRef<DailyCall | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [loading, setLoading] = useState(true);
  const [errorInfo, setErrorInfo] = useState<SessionErrorInfo | null>(null);
  const [isOwner, setIsOwner] = useState(false);

  // Sign-off / settlement state
  const [settling, setSettling] = useState(false);
  const [settleStatus, setSettleStatus] = useState<SignOffResponse | null>(null);
  const [showSignOffModal, setShowSignOffModal] = useState(false);

  // Stop heartbeat safely
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // Start heartbeat every 10s
  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatTimerRef.current = setInterval(async () => {
      try {
        await sendSessionHeartbeat(bookingId);
      } catch {
        // Silently tolerate brief transient connection blips
      }
    }, 10000);
  }, [bookingId, stopHeartbeat]);

  useEffect(() => {
    let mounted = true;

    async function initSession() {
      if (!bookingId) return;
      try {
        setLoading(true);
        setErrorInfo(null);

        // Fetch join parameters & token from backend
        const data = await joinVideoSession(bookingId);
        if (!mounted) return;

        setIsOwner(data.is_owner);

        if (!containerRef.current) return;

        // Initialize Daily call frame
        const callFrame = DailyIframe.createFrame(containerRef.current, {
          iframeStyle: {
            width: "100%",
            height: "100%",
            border: "none",
            borderRadius: "16px",
          },
          showLeaveButton: true,
          showFullscreenButton: true,
        });

        callFrameRef.current = callFrame;

        // Lifecycle event listeners
        callFrame.on("joined-meeting", () => {
          if (!mounted) return;
          startHeartbeat();
        });

        callFrame.on("left-meeting", () => {
          if (!mounted) return;
          stopHeartbeat();
        });

        callFrame.on("error", (e) => {
          console.error("Daily.co frame error:", e);
        });

        // Join room using Daily-js API (token is passed directly in payload, NEVER embedded in iframe url)
        await callFrame.join({
          url: data.url,
          token: data.token,
        });

        if (mounted) setLoading(false);
      } catch (err: unknown) {
        if (!mounted) return;
        setLoading(false);
        const info = formatSessionErrorMessage(err);
        setErrorInfo(info);
      }
    }

    initSession();

    return () => {
      mounted = false;
      stopHeartbeat();
      if (callFrameRef.current) {
        callFrameRef.current.destroy();
        callFrameRef.current = null;
      }
    };
  }, [bookingId, startHeartbeat, stopHeartbeat]);

  const handleSignOff = async () => {
    try {
      setSettling(true);
      const res = await signOffBooking(bookingId);
      setSettleStatus(res);
      setShowSignOffModal(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Sign-off failed");
    } finally {
      setSettling(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Session Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            href="/dashboard"
            className="flex items-center text-sm font-medium text-slate-400 hover:text-white transition"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Dashboard
          </Link>
          <div className="h-4 w-px bg-slate-800" />
          <div className="flex items-center space-x-2">
            <Video className="w-5 h-5 text-indigo-400" />
            <h1 className="text-base font-semibold text-white">Live Mentoring Session</h1>
            {isOwner ? (
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Mentor
              </span>
            ) : (
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Learner
              </span>
            )}
          </div>
        </div>

        {/* Top actions: Sign-off settlement */}
        <div className="flex items-center space-x-3">
          {settleStatus?.status === "settled" ? (
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm font-medium">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>Session Settled</span>
            </div>
          ) : settleStatus?.status === "waiting_for_other_party" ? (
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm font-medium">
              <Clock className="w-4 h-4 text-amber-400 animate-spin" />
              <span>Waiting for Counterpart</span>
            </div>
          ) : (
            <button
              onClick={() => setShowSignOffModal(true)}
              className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl text-white bg-indigo-600 hover:bg-indigo-500 transition shadow-sm border border-indigo-500/30"
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Complete & Settle
            </button>
          )}
        </div>
      </header>

      {/* Settlement Status Banner */}
      {settleStatus && (
        <div
          className={`px-6 py-3 border-b text-sm font-medium flex items-center justify-between ${
            settleStatus.status === "settled"
              ? "bg-emerald-950/60 border-emerald-800 text-emerald-200"
              : "bg-amber-950/60 border-amber-800 text-amber-200"
          }`}
        >
          <div className="flex items-center space-x-2">
            {settleStatus.status === "settled" ? (
              <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <Clock className="w-5 h-5 text-amber-400 shrink-0" />
            )}
            <span>
              {settleStatus.status === "settled"
                ? "Both parties confirmed sign-off. Escrow credits released to the mentor."
                : "You have signed off. Waiting for the other participant to confirm settlement."}
            </span>
          </div>

          {settleStatus.status === "settled" && settleStatus.audit_passed === true && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-emerald-900/60 text-emerald-300 border border-emerald-700">
              <Shield className="w-3 h-3 mr-1" />
              Ledger Audit Verified
            </span>
          )}

          {settleStatus.status === "settled" && settleStatus.audit_passed === false && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-rose-900/60 text-rose-300 border border-rose-700">
              <AlertCircle className="w-3 h-3 mr-1" />
              Settled (Admin Drift Alert Logged)
            </span>
          )}
        </div>
      )}

      {/* Main Video Call Area */}
      <main className="flex-1 p-4 flex flex-col items-center justify-center relative">
        {loading && (
          <div className="flex flex-col items-center justify-center p-8 space-y-4 text-center">
            <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
            <h2 className="text-lg font-medium text-slate-200">Entering Video Room...</h2>
            <p className="text-sm text-slate-400 max-w-sm">
              Establishing end-to-end encrypted WebRTC media session on Daily.co.
            </p>
          </div>
        )}

        {errorInfo && (
          <div className="max-w-md w-full bg-slate-900 border border-rose-900/60 rounded-2xl p-6 text-center space-y-4 shadow-xl">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 mx-auto flex items-center justify-center">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">{errorInfo.title}</h3>
              <p className="mt-2 text-sm text-slate-300 leading-relaxed">{errorInfo.description}</p>
            </div>
            <div className="pt-2 flex items-center justify-center gap-3">
              <Link
                href="/dashboard"
                className="inline-flex items-center px-4 py-2 rounded-xl bg-slate-800 text-slate-200 hover:bg-slate-700 text-sm font-medium transition cursor-pointer"
              >
                Return to Dashboard
              </Link>
            </div>
          </div>
        )}

        {/* Daily.co Call Frame Container */}
        <div
          ref={containerRef}
          className={`w-full flex-1 min-h-[600px] rounded-2xl overflow-hidden bg-slate-900 border border-slate-800/80 shadow-2xl transition-opacity duration-300 ${
            loading || errorInfo ? "hidden" : "block"
          }`}
        />
      </main>

      {/* Sign-Off Confirmation Modal */}
      {showSignOffModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center space-x-3 text-indigo-400">
              <Shield className="w-6 h-6" />
              <h3 className="text-lg font-semibold text-white">Sign Off & Settle Session</h3>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Signing off confirms that the peer mentoring session has completed. Once both you and
              your counterpart sign off, the escrowed credits will be permanently released to the
              mentor and audited in the ledger.
            </p>
            <div className="bg-slate-950/60 rounded-xl p-3 text-xs text-slate-400 border border-slate-800">
              Note: Early sign-offs are blocked before scheduled session start time.
            </div>
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setShowSignOffModal(false)}
                className="px-4 py-2 rounded-xl text-sm font-medium text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={settling}
                onClick={handleSignOff}
                className="inline-flex items-center px-4 py-2 rounded-xl text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 transition disabled:opacity-50"
              >
                {settling ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Signing Off...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Confirm Sign-Off
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
