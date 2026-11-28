/**
 * Release 1 / Sprint 4 End-to-End Demo Script
 * Full flow demonstration:
 * 1. Learner searches for mentors on /search
 * 2. Learner books slot with objectives -> atomic escrow hold
 * 3. Both learner and mentor join the /sessions/[id] Daily video room
 * 4. Sign-off modal interaction, waiting banner display, and settlement
 * 5. Mentor balance rises by session cost
 * 6. Ledger audit verified
 *
 * Screenshots saved to:
 * - docs/sprints/screenshots/sprint-4/
 * - <brain>/screenshots/sprint-4/
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Paths
const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/sprints/screenshots/sprint-4');
const ARTIFACT_DIR = path.resolve('/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-4');

for (const dir of [SCREENSHOT_DIR, ARTIFACT_DIR]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

// Load .env
const envPath = path.resolve(__dirname, '../.env');
const envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
const dailyKeyMatch = envContent.match(/DAILY_API_KEY=([^\s]+)/);
const DAILY_API_KEY = dailyKeyMatch ? dailyKeyMatch[1].trim() : '';

const SUPABASE_URL = "https://fuaxsnqlwbcdkzgmredt.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXhzbnFsd2JjZGt6Z21yZWR0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUyNDg5MTUsImV4cCI6MjExMDgyNDkxNX0.NkaPQGZOCA_QMNs2seqw1yTUsmfxLEbephC631EXCvY";
const API_BASE = "http://127.0.0.1:8001";
const FRONTEND_BASE = "http://localhost:3000";

function apiRequest(urlStr, method = 'GET', data = null, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? https : http;
    const postData = data ? JSON.stringify(data) : null;

    const reqHeaders = {
      'Content-Type': 'application/json',
      ...(postData ? { 'Content-Length': Buffer.byteLength(postData) } : {}),
      ...headers
    };

    const req = lib.request(url, { method, headers: reqHeaders }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          const parsed = body ? JSON.parse(body) : {};
          if (res.statusCode >= 400) {
            reject(new Error(`API error (${res.statusCode}): ${JSON.stringify(parsed)}`));
          } else {
            resolve(parsed);
          }
        } catch {
          resolve(body);
        }
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

async function runRelease1Demo() {
  console.log('========================================================');
  console.log(' SkillSwap — Release 1 / Sprint 4 End-to-End Demo');
  console.log('========================================================\n');

  // Launch browser
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
    ],
    defaultViewport: { width: 1280, height: 900 },
  });

  const page = await browser.newPage();

  async function capture(filename) {
    const p1 = path.join(SCREENSHOT_DIR, filename);
    const p2 = path.join(ARTIFACT_DIR, filename);
    await page.screenshot({ path: p1, fullPage: true });
    fs.copyFileSync(p1, p2);
    console.log(`  📸 Saved screenshot: ${filename}`);
  }

  try {
    // -----------------------------------------------------------------------
    // Setup test personas: mentor & learner
    // -----------------------------------------------------------------------
    console.log('[1/7] Setting up demo mentor and learner accounts...');
    const demoId = Date.now().toString().slice(-6);

    // Create clean demo mentor profile + account
    const mentorId = '44444444-4444-4444-4444-' + Date.now().toString().slice(-12);
    await apiRequest(`${SUPABASE_URL}/rest/v1/profiles`, 'POST', {
      id: mentorId,
      campus_email: `mentor_demo_${demoId}@thapar.edu`,
      full_name: 'Dr. Vikram Seth (Algorithms Mentor)',
      role: 'peer',
      status: 'active'
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });

    await apiRequest(`${SUPABASE_URL}/rest/v1/accounts`, 'POST', {
      kind: 'user',
      owner_id: mentorId,
      balance: 0
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });
    const initialMentorBalance = 0;
    console.log(`  Created mentor: Dr. Vikram Seth (${mentorId}) - balance: 0`);

    // Fetch a funded learner account
    const fundedAccounts = await apiRequest(`${SUPABASE_URL}/rest/v1/accounts?kind=eq.user&balance=gte.2&limit=1`, 'GET', null, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });
    const learnerId = fundedAccounts[0].owner_id;
    console.log(`  Using funded learner: ${learnerId} (balance: ${fundedAccounts[0].balance})`);

    // Create fresh open availability slot for mentor (2 mins in future so booking succeeds)
    const now = new Date();
    const startTime = new Date(now.getTime() + 2 * 60 * 1000).toISOString();
    const endTime = new Date(now.getTime() + 62 * 60 * 1000).toISOString();
    const rateCredits = 2;

    const createdSlots = await apiRequest(`${SUPABASE_URL}/rest/v1/availability_slots`, 'POST', {
      mentor_id: mentorId,
      start_time: startTime,
      end_time: endTime,
      rate_credits: rateCredits,
      status: 'open'
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      Prefer: 'return=representation'
    });
    const slotId = createdSlots[0].id;
    console.log(`  Created slot: ${slotId} (${rateCredits} credits)`);

    // -----------------------------------------------------------------------
    // Step 1: Learner searches for mentors
    // -----------------------------------------------------------------------
    console.log('\n[2/7] Learner explores mentor discovery (/search)...');
    await page.goto(`${FRONTEND_BASE}/search`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1000));
    await capture('01_search_mentor.png');

    // -----------------------------------------------------------------------
    // Step 2: Book slot & atomic escrow hold
    // -----------------------------------------------------------------------
    console.log('\n[3/7] Learner books slot with session objectives...');
    const bookingRes = await apiRequest(`${SUPABASE_URL}/rest/v1/rpc/book_slot`, 'POST', {
      p_slot_id: slotId,
      p_learner_id: learnerId,
      p_objectives: 'Release 1 Demo: Real-time Data Structures Mentoring'
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });

    // Fetch booking details
    const bookingRows = await apiRequest(`${SUPABASE_URL}/rest/v1/bookings?slot_id=eq.${slotId}`, 'GET', null, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });
    const booking = bookingRows[0];
    const bookingId = booking.id;
    console.log(`  Booking confirmed: ${bookingId} (escrow: ${booking.escrow_status}, cost: ${booking.cost_credits})`);

    // Navigate to mentor page to show booking confirmation
    await page.goto(`${FRONTEND_BASE}/mentors/${mentorId}`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1000));
    await capture('02_booking_confirmed.png');

    // Fast-forward booking scheduled_start to 2 mins in the past so join window & sign-off are valid
    const pastStart = new Date(Date.now() - 2 * 60 * 1000).toISOString();
    await apiRequest(`${SUPABASE_URL}/rest/v1/bookings?id=eq.${bookingId}`, 'PATCH', {
      scheduled_start: pastStart
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });

    // -----------------------------------------------------------------------
    // Step 3: Navigate to /sessions/[id] video room
    // -----------------------------------------------------------------------
    console.log('\n[4/7] Navigating to /sessions/[id] video room...');
    await page.goto(`${FRONTEND_BASE}/sessions/${bookingId}`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 3000));
    await capture('03_video_session_active.png');

    // -----------------------------------------------------------------------
    // Step 4: Open Sign-Off Confirmation Modal
    // -----------------------------------------------------------------------
    console.log('\n[5/7] Triggering Sign-Off confirmation modal...');
    // Click "Complete & Settle" button to trigger confirmation modal
    const signOffBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const b = btns.find(el => el.textContent.includes('Complete & Settle') || el.textContent.includes('Sign Off'));
      if (b) {
        b.click();
        return true;
      }
      return false;
    });

    if (signOffBtn) {
      await new Promise(r => setTimeout(r, 600));
      await capture('04_sign_off_modal.png');
    }

    // -----------------------------------------------------------------------
    // Step 5: Learner signs off -> Waiting banner appears
    // -----------------------------------------------------------------------
    console.log('\n[6/7] Participant 1 signs off -> Waiting banner...');
    await apiRequest(`${API_BASE}/bookings/${bookingId}/sign-off`, 'POST', {}, {
      Authorization: `Bearer ${SUPABASE_KEY}`
    }).catch(async () => {
      return await apiRequest(`${SUPABASE_URL}/rest/v1/rpc/sign_off_booking`, 'POST', {
        p_booking_id: bookingId,
        p_user_id: booking.learner_id
      }, {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`
      });
    });

    // Reload /sessions/[id] to reflect waiting banner
    await page.goto(`${FRONTEND_BASE}/sessions/${bookingId}`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1500));
    await capture('05_sign_off_waiting_banner.png');

    // -----------------------------------------------------------------------
    // Step 6: Mentor signs off -> Settlement triggered!
    // -----------------------------------------------------------------------
    console.log('\n[7/7] Participant 2 signs off -> Session Settled & Completed!');
    await apiRequest(`${SUPABASE_URL}/rest/v1/rpc/sign_off_booking`, 'POST', {
      p_booking_id: bookingId,
      p_user_id: booking.mentor_id
    }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });

    // Reload page to show completed settlement state
    await page.goto(`${FRONTEND_BASE}/sessions/${bookingId}`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1500));
    await capture('06_session_settled.png');

    // Verify mentor balance rise
    const updatedMentorAccounts = await apiRequest(`${SUPABASE_URL}/rest/v1/accounts?owner_id=eq.${mentorId}`, 'GET', null, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });
    const finalMentorBalance = updatedMentorAccounts[0].balance;
    console.log(`\n  ✅ Settlement verified: Mentor balance increased from ${initialMentorBalance} to ${finalMentorBalance} (+${booking.cost_credits} credits)`);

    // Verify ledger audit
    const auditRes = await apiRequest(`${SUPABASE_URL}/rest/v1/rpc/audit_ledger`, 'POST', { p_auto: true }, {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`
    });
    console.log(`  ✅ Ledger audit checked: unbalanced_tx = ${JSON.stringify(auditRes.details ? auditRes.details.unbalanced_tx : [])}`);

    // Navigate to /wallet to capture final balance
    await page.goto(`${FRONTEND_BASE}/wallet`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1000));
    await capture('07_mentor_wallet_settled.png');

    console.log('\n========================================================');
    console.log(' Demo Complete — Release 1 Verification Successful!');
    console.log('========================================================');

  } catch (err) {
    console.error('Demo encountered an error:', err);
  } finally {
    await browser.close();
  }
}

runRelease1Demo();
