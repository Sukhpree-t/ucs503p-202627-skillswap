/**
 * Session Error Mapping & Formatting (US-14 / Sprint 4)
 * Provides user-friendly plain-language explanations for room join failures,
 * with times formatted in the user's local timezone.
 */

export interface SessionErrorInfo {
  code: string;
  title: string;
  description: string;
}

export function formatSessionErrorMessage(
  rawError: unknown,
  scheduledStartFallback?: string | null
): SessionErrorInfo {
  let message = "";
  if (typeof rawError === "string") {
    message = rawError;
  } else if (rawError instanceof Error) {
    message = rawError.message;
  } else if (rawError && typeof rawError === "object" && "message" in rawError) {
    message = String((rawError as { message: unknown }).message);
  }

  const normalized = message.toUpperCase();

  // 1. ROOM_CREATION_FAILED (Check before general escrow check)
  if (normalized.includes("ROOM_CREATION_FAILED")) {
    return {
      code: "ROOM_CREATION_FAILED",
      title: "Video Room Unavailable",
      description: "We couldn't create the video room. You were not charged.",
    };
  }

  // 2. SESSION_NOT_STARTED: "The room opens 10 minutes before the session. It starts at <local time>."
  if (normalized.includes("SESSION_NOT_STARTED")) {
    let startTimeIso = scheduledStartFallback;
    // Extract ISO timestamp if present in error string
    const match = message.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:[0-9.]+(?:Z|[+-]\d{2}:\d{2})/i);
    if (match) {
      startTimeIso = match[0];
    }

    let timeStr = "";
    if (startTimeIso) {
      try {
        const d = new Date(startTimeIso);
        timeStr = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      } catch {
        timeStr = startTimeIso;
      }
    }

    const description = timeStr
      ? `The room opens 10 minutes before the session. It starts at ${timeStr}.`
      : "The room opens 10 minutes before the session.";

    return {
      code: "SESSION_NOT_STARTED",
      title: "Session Has Not Started",
      description,
    };
  }

  // 3. SESSION_WINDOW_EXPIRED
  if (normalized.includes("SESSION_WINDOW_EXPIRED") || (normalized.includes("EXPIRED") && !normalized.includes("TOKEN"))) {
    return {
      code: "SESSION_WINDOW_EXPIRED",
      title: "Session Window Expired",
      description: "This session window has closed. The meeting room is no longer accessible.",
    };
  }

  // 4. ESCROW_NOT_HELD
  if (normalized.includes("ESCROW_NOT_HELD") || normalized.includes("ESCROW")) {
    return {
      code: "ESCROW_NOT_HELD",
      title: "Escrow Inactive",
      description: "This session's escrow is no longer active. The credits have already been settled or refunded.",
    };
  }

  // 5. UNAUTHORIZED_PARTICIPANT
  if (
    normalized.includes("UNAUTHORIZED_PARTICIPANT") ||
    normalized.includes("NOT A PARTICIPANT") ||
    normalized.includes("NOT PART OF THIS BOOKING")
  ) {
    return {
      code: "UNAUTHORIZED_PARTICIPANT",
      title: "Access Restricted",
      description: "You are not a registered participant for this mentoring session. Please switch to the account that booked or is mentoring this session.",
    };
  }

  // 6. Network / server unreachable
  if (
    normalized.includes("FAILED TO FETCH") ||
    normalized.includes("NETWORKERROR") ||
    normalized.includes("ERR_CONNECTION") ||
    normalized.includes("CONNECTION REFUSED") ||
    normalized.includes("502") ||
    normalized.includes("504") ||
    normalized.includes("SERVER UNREACHABLE") ||
    normalized.includes("NETWORK OR SERVER UNREACHABLE")
  ) {
    return {
      code: "NETWORK_ERROR",
      title: "Connection Error",
      description: "Network or server unreachable. Please check your connection and try again.",
    };
  }

  // Fallback
  return {
    code: "UNKNOWN_ERROR",
    title: "Unable to Enter Room",
    description: message || "Failed to join session. Please try again or return to your dashboard.",
  };
}
