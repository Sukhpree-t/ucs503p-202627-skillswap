#!/usr/bin/env node
/**
 * scripts/make_joinable_booking.js
 *
 * Dev-only utility that creates a live joinable session between demo users:
 * - Mentor: Alex Vance (alex.vance@campus.edu)
 * - Learner: Maya Patel (maya.patel@campus.edu)
 *
 * The booking scheduled_start is set to (now + 3 minutes), which falls directly
 * inside the 10-minute early-join window (now >= scheduled_start - 10 min),
 * making the Daily.co video room IMMEDIATELY joinable without any waiting.
 *
 * SAFETY GUARD: Refuses to execute if NODE_ENV=production or APP_ENV=production.
 */

const API_BASE = process.env.API_BASE || 'http://127.0.0.1:8001';
const FRONTEND_BASE = process.env.FRONTEND_BASE || 'http://localhost:3000';

// 1. Production safety check
if (
  process.env.NODE_ENV === 'production' ||
  process.env.APP_ENV === 'production' ||
  process.env.VERCEL_ENV === 'production' ||
  process.env.ENVIRONMENT === 'production'
) {
  console.error('\x1b[31m%s\x1b[0m', 'CRITICAL: scripts/make_joinable_booking.js is a dev-only utility and cannot be run in production.');
  process.exit(1);
}

async function apiRequest(endpoint, method = 'GET', body = null, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const opts = { method, headers };
  if (body) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${endpoint}`, opts);
  if (!res.ok) {
    let errBody = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      errBody = j.detail || j.message || JSON.stringify(j);
    } catch {
      errBody = await res.text();
    }
    throw new Error(`API ${method} ${endpoint} failed (${res.status}): ${errBody}`);
  }
  return res.json();
}

async function main() {
  console.log('\x1b[36m%s\x1b[0m', '=== SkillSwap: Creating Dev Joinable Booking ===\n');

  // Step 1: Login Mentor (Alex Vance)
  console.log('1. Signing in as Mentor (Alex Vance)...');
  const mentorAuth = await apiRequest('/auth/campus-sso', 'POST', {
    email: 'alex.vance@campus.edu',
    full_name: 'Alex Vance',
    department: 'Computer Science & Engineering',
    study_year: 3,
  });
  const mentorToken = mentorAuth.token;
  console.log(`   Logged in: ${mentorAuth.user.full_name} (${mentorAuth.user.id})`);

  // Step 2: Login Learner (Maya Patel)
  console.log('2. Signing in as Learner (Maya Patel)...');
  const learnerAuth = await apiRequest('/auth/campus-sso', 'POST', {
    email: 'maya.patel@campus.edu',
    full_name: 'Maya Patel',
    department: 'Electronics & Communication',
    study_year: 2,
  });
  const learnerToken = learnerAuth.token;
  console.log(`   Logged in: ${learnerAuth.user.full_name} (${learnerAuth.user.id})`);

  // Step 3: Clean up previous open slots and create fresh slot starting in ~3 minutes
  const now = new Date();
  const startTime = new Date(now.getTime() + 3 * 60 * 1000); // +3 min
  const endTime = new Date(now.getTime() + 63 * 60 * 1000);  // +63 min

  console.log('3. Preparing fresh availability slot for Mentor...');
  const mySlots = await apiRequest('/slots/mine', 'GET', null, mentorToken);
  for (const s of mySlots) {
    if (s.status === 'open') {
      try {
        await apiRequest(`/slots/${s.id}`, 'DELETE', null, mentorToken);
        console.log(`   Cleaned up prior open slot: ${s.id}`);
      } catch {
        // ignore
      }
    }
  }

  const scheduled_start = startTime.toISOString();
  const scheduled_end = endTime.toISOString();
  console.log(`   scheduled_start: ${scheduled_start} (${startTime.toLocaleTimeString()} local)`);
  console.log(`   scheduled_end:   ${scheduled_end} (${endTime.toLocaleTimeString()} local)`);

  const slot = await apiRequest(
    '/slots',
    'POST',
    {
      start_time: scheduled_start,
      end_time: scheduled_end,
      rate_credits: 1,
    },
    mentorToken
  );
  console.log(`   Fresh Slot Created: ${slot.id}`);

  // Step 4: Book slot as Learner (locks 1 escrow credit)
  console.log('4. Booking slot as Learner (Maya Patel)...');
  const bookingRes = await apiRequest(
    '/booking',
    'POST',
    {
      slot_id: slot.id,
      objectives: 'Live Video Call & Mutual Sign-off Verification',
    },
    learnerToken
  );
  const bookingId = bookingRes.booking_id;
  console.log(`   Booking Confirmed: ${bookingId}`);

  // Summary
  console.log('\n\x1b[32m%s\x1b[0m', 'SUCCESS: Immediate Joinable Booking Ready!');
  console.log('-------------------------------------------------------------');
  console.log(`Booking ID:       ${bookingId}`);
  console.log(`scheduled_start:  ${scheduled_start}`);
  console.log(`scheduled_end:    ${scheduled_end}`);
  console.log(`Session Room:     ${FRONTEND_BASE}/sessions/${bookingId}`);
  console.log(`Join Window:      Open NOW (opens 10m before start, ends 15m after end)`);
  console.log('-------------------------------------------------------------');
  console.log('To test in 2 browser windows:');
  console.log(`1. Window 1 (Mentor):  Login as Alex Vance -> Open ${FRONTEND_BASE}/sessions/${bookingId}`);
  console.log(`2. Window 2 (Learner): Login as Maya Patel -> Open ${FRONTEND_BASE}/sessions/${bookingId}`);
  console.log('-------------------------------------------------------------\n');
}

main().catch((err) => {
  console.error('\x1b[31m%s\x1b[0m', `Failed to create joinable booking: ${err.message}`);
  process.exit(1);
});
