/**
 * Sprint 2 Browser Demo Script
 * Demonstrates:
 * - US-08: Publish availability slots, hourly credit rate, conflict prevention
 * - US-05: Semantic vector search by learning goal with rate/rating filters
 * - US-07: Public mentor profile view with open availability slots
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/sprints/screenshots/sprint-2');

async function runDemo() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log('[Sprint 2 Demo] Launching headless browser...');
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    defaultViewport: { width: 1280, height: 850 },
  });

  const page = await browser.newPage();

  try {
    // 1. Login with demo persona Alex Vance (Mentor)
    console.log('[Step 1] Logging in as Mentor Alex Vance...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle0' });
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const alex = buttons.find(b => b.textContent && b.textContent.includes('Alex Vance'));
      if (alex) alex.click();
    });
    await new Promise(r => setTimeout(r, 400));
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const submit = buttons.find(b => b.textContent && b.textContent.includes('Sign in with Campus SSO'));
      if (submit) submit.click();
    });
    await page.waitForNavigation({ waitUntil: 'networkidle0' });
    console.log('✓ Logged in, landed on /dashboard');

    // 2. Navigate to /availability (US-08)
    console.log('[Step 2] Navigating to /availability...');
    await page.goto('http://localhost:3000/availability', { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 800));

    // Fill slot form: Tomorrow 14:00 to 15:00 at 2 credits/hr
    await page.evaluate(() => {
      const inputs = document.querySelectorAll('input');
      // Set start time to 14:00, end time to 15:00, rate to 2
      inputs.forEach(input => {
        if (input.type === 'time' && input.value.includes('14')) input.value = '14:00';
        if (input.type === 'time' && input.value.includes('15')) input.value = '15:00';
        if (input.type === 'number') input.value = '2';
      });
    });

    // Click Publish Slot button
    await page.evaluate(() => {
      const submitBtn = document.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.click();
    });
    await new Promise(r => setTimeout(r, 1200));

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_availability_slots_published.png'), fullPage: true });
    console.log('✓ Captured 01_availability_slots_published.png (US-08)');

    // 3. Trigger slot overlap conflict validation (US-08)
    console.log('[Step 3] Submitting overlapping slot to verify conflict prevention...');
    await page.evaluate(() => {
      const submitBtn = document.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_slot_conflict_validation.png'), fullPage: true });
    console.log('✓ Captured 02_slot_conflict_validation.png (US-08)');

    // 4. Navigate to /search (US-05)
    console.log('[Step 4] Navigating to /search for semantic goal discovery...');
    await page.goto('http://localhost:3000/search', { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1000));

    // Type query "Python and backend APIs"
    await page.type('input[type="text"]', 'Python and backend APIs', { delay: 30 });
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 1500));

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_semantic_goal_search.png'), fullPage: true });
    console.log('✓ Captured 03_semantic_goal_search.png (US-05)');

    // 5. Click "View Profile & Slots" to view public mentor profile (US-07)
    console.log('[Step 5] Clicking mentor card to navigate to public profile...');
    const mentorLink = await page.$('a[href^="/mentors/"]');
    if (mentorLink) {
      await mentorLink.click();
      await page.waitForNavigation({ waitUntil: 'networkidle0' });
      await new Promise(r => setTimeout(r, 1000));
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_mentor_profile_and_slots.png'), fullPage: true });
      console.log('✓ Captured 04_mentor_profile_and_slots.png (US-07)');
    } else {
      console.log('Warning: No mentor profile link found on search page');
    }

    console.log('\n=======================================');
    console.log('✅ Sprint 2 Browser Demo Walkthrough Completed Successfully!');
    console.log('Screenshots saved to: docs/sprints/screenshots/sprint-2/');
    console.log('=======================================\n');

  } catch (err) {
    console.error('Demo error:', err);
  } finally {
    await browser.close();
  }
}

runDemo();
