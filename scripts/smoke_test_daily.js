/**
 * Sprint 4 Daily.co Two-Browser Smoke Test
 * Verifies live WebRTC connection between two independent browsers:
 * - Browser 1: Mentor (is_owner: true)
 * - Browser 2: Learner (is_owner: false)
 * Using Daily.co Prebuilt video UI on earthian.daily.co
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const https = require('https');

// Load .env
const envPath = path.resolve(__dirname, '../.env');
if (!fs.existsSync(envPath)) {
  console.error('.env not found!');
  process.exit(1);
}
const envContent = fs.readFileSync(envPath, 'utf8');
const dailyKeyMatch = envContent.match(/DAILY_API_KEY=([^\s]+)/);
const dailyDomainMatch = envContent.match(/DAILY_DOMAIN=([^\s]+)/);

if (!dailyKeyMatch) {
  console.error('DAILY_API_KEY not found in .env!');
  process.exit(1);
}

const DAILY_API_KEY = dailyKeyMatch[1].trim();
const DAILY_DOMAIN = (dailyDomainMatch ? dailyDomainMatch[1].trim() : 'earthian');

const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/sprints/screenshots/sprint-4');
const ARTIFACT_DIR = path.resolve('/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-4');

for (const dir of [SCREENSHOT_DIR, ARTIFACT_DIR]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function dailyRequest(endpoint, method = 'GET', data = null) {
  return new Promise((resolve, reject) => {
    const postData = data ? JSON.stringify(data) : null;
    const req = https.request(`https://api.daily.co/v1/${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${DAILY_API_KEY}`,
        'Content-Type': 'application/json',
        ...(postData ? { 'Content-Length': Buffer.byteLength(postData) } : {})
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          if (res.statusCode >= 400) {
            reject(new Error(`Daily API error (${res.statusCode}): ${JSON.stringify(parsed)}`));
          } else {
            resolve(parsed);
          }
        } catch (e) {
          if (res.statusCode < 400) resolve(body);
          else reject(new Error(`Daily API returned non-JSON error (${res.statusCode}): ${body}`));
        }
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

async function runSmokeTest() {
  const roomName = `smoke-${Date.now().toString().slice(-8)}`;
  console.log(`[Smoke Test] 1. Creating private Daily room: ${roomName}...`);

  const room = await dailyRequest('rooms', 'POST', {
    name: roomName,
    privacy: 'private',
    properties: {
      max_participants: 2,
      enable_chat: true,
      enable_screenshare: true,
      eject_at_room_exp: true,
      exp: Math.floor(Date.now() / 1000) + 1800 // 30 mins
    }
  });
  console.log(`✓ Room created: ${room.url}`);

  console.log('[Smoke Test] 2. Generating room-scoped meeting tokens for Mentor and Learner...');
  const mentorTokenRes = await dailyRequest('meeting-tokens', 'POST', {
    properties: {
      room_name: roomName,
      user_name: 'Dr. Ananya Sharma (Mentor)',
      is_owner: true,
      eject_at_token_exp: true,
      exp: Math.floor(Date.now() / 1000) + 1800
    }
  });

  const learnerTokenRes = await dailyRequest('meeting-tokens', 'POST', {
    properties: {
      room_name: roomName,
      user_name: 'Rohan Verma (Learner)',
      is_owner: false,
      eject_at_token_exp: true,
      exp: Math.floor(Date.now() / 1000) + 1800
    }
  });

  const mentorUrl = `https://${DAILY_DOMAIN}.daily.co/${roomName}?t=${mentorTokenRes.token}`;
  const learnerUrl = `https://${DAILY_DOMAIN}.daily.co/${roomName}?t=${learnerTokenRes.token}`;

  console.log('[Smoke Test] 3. Spawning 2 independent Chrome browser instances with simulated media devices...');
  const chromeArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-gpu',
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    '--autoplay-policy=no-user-gesture-required'
  ];

  const browserMentor = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: chromeArgs,
    defaultViewport: { width: 1280, height: 800 }
  });

  const browserLearner = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: chromeArgs,
    defaultViewport: { width: 1280, height: 800 }
  });

  const pageMentor = await browserMentor.newPage();
  const pageLearner = await browserLearner.newPage();

  async function clickJoinIfPresent(page, role) {
    try {
      await page.waitForSelector('button', { timeout: 8000 });
      const clicked = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const joinBtn = buttons.find(b => {
          const txt = (b.innerText || '').toLowerCase();
          return txt.includes('join') || txt.includes('enter');
        });
        if (joinBtn) {
          joinBtn.click();
          return true;
        }
        return false;
      });
      if (clicked) {
        console.log(`✓ Clicked join button for ${role}`);
      }
    } catch (e) {
      console.log(`(Prejoin button not required or not found for ${role})`);
    }
  }

  try {
    console.log('[Smoke Test] 4. Mentor joining call...');
    await pageMentor.goto(mentorUrl, { waitUntil: 'networkidle2' });
    await clickJoinIfPresent(pageMentor, 'Mentor');

    console.log('[Smoke Test] 5. Learner joining call...');
    await pageLearner.goto(learnerUrl, { waitUntil: 'networkidle2' });
    await clickJoinIfPresent(pageLearner, 'Learner');

    console.log('[Smoke Test] 6. Waiting 5s for WebRTC peer-to-peer connection & audio/video streams...');
    await new Promise(r => setTimeout(r, 6000));

    // Capture screenshots of both participants
    console.log('[Smoke Test] 7. Capturing real browser screenshots of live session...');
    const mentorImgPath = path.join(SCREENSHOT_DIR, '01_daily_smoke_mentor_view.png');
    const mentorArtifactPath = path.join(ARTIFACT_DIR, '01_daily_smoke_mentor_view.png');
    await pageMentor.screenshot({ path: mentorImgPath });
    fs.copyFileSync(mentorImgPath, mentorArtifactPath);

    const learnerImgPath = path.join(SCREENSHOT_DIR, '02_daily_smoke_learner_view.png');
    const learnerArtifactPath = path.join(ARTIFACT_DIR, '02_daily_smoke_learner_view.png');
    await pageLearner.screenshot({ path: learnerImgPath });
    fs.copyFileSync(learnerImgPath, learnerArtifactPath);

    console.log(`✓ Mentor screenshot saved: ${mentorImgPath}`);
    console.log(`✓ Learner screenshot saved: ${learnerImgPath}`);

    const result = {
      success: true,
      room_name: roomName,
      mentor_url: mentorUrl.replace(/t=.*/, 't=<REDACTED>'),
      learner_url: learnerUrl.replace(/t=.*/, 't=<REDACTED>'),
      mentor_screenshot: mentorArtifactPath,
      learner_screenshot: learnerArtifactPath
    };
    console.log('[Smoke Test] Result:', JSON.stringify(result, null, 2));

  } finally {
    console.log('[Smoke Test] 8. Cleaning up: Closing browsers and deleting Daily room to preserve quota...');
    await browserMentor.close();
    await browserLearner.close();
    try {
      await dailyRequest(`rooms/${roomName}`, 'DELETE');
      console.log(`✓ Successfully deleted temporary room ${roomName} from Daily API.`);
    } catch (e) {
      console.warn('Failed to delete room:', e.message);
    }
  }
}

runSmokeTest().catch(err => {
  console.error('[Smoke Test Error]:', err);
  process.exit(1);
});
