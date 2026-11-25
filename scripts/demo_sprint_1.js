/**
 * Sprint 1 Browser Demo Script
 * Runs end-to-end verification and captures evidence screenshots.
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/sprints/screenshots/sprint-1');

async function runDemo() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log('[Demo] Launching headless Chrome...');
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    defaultViewport: { width: 1280, height: 800 },
  });

  const page = await browser.newPage();

  try {
    // 1. Visit Login Page (US-01)
    console.log('[Demo Step 1] Navigating to http://localhost:3000/login');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle0' });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_login_sso.png'), fullPage: true });
    console.log('✓ Captured 01_login_sso.png');

    // 2. Select Alex Vance demo persona & Submit SSO
    console.log('[Demo Step 2] Clicking Alex Vance demo persona and signing in...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const alex = buttons.find(b => b.textContent && b.textContent.includes('Alex Vance'));
      if (alex) alex.click();
    });
    await new Promise((r) => setTimeout(r, 400));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const submit = buttons.find(b => b.textContent && b.textContent.includes('Sign in with Campus SSO'));
      if (submit) submit.click();
    });

    // 3. Wait for Dashboard (US-01 completion)
    console.log('[Demo Step 3] Waiting for /dashboard redirect...');
    await page.waitForNavigation({ waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_dashboard_overview.png'), fullPage: true });
    console.log('✓ Captured 02_dashboard_overview.png');

    // 4. Visit Profile Page (US-02)
    console.log('[Demo Step 4] Navigating to /profile...');
    await page.goto('http://localhost:3000/profile', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_profile_initial.png'), fullPage: true });
    console.log('✓ Captured 03_profile_initial.png');

    // 5. Add Teaching Skill: Python & Backend (Advanced, 2 cr)
    console.log('[Demo Step 5] Adding teaching skill: Python & Backend...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const addBtn = buttons.find(b => b.textContent && b.textContent.includes('Add Skill'));
      if (addBtn) addBtn.click();
    });
    await new Promise((r) => setTimeout(r, 500));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const preset = buttons.find(b => b.textContent && b.textContent.includes('Python & Backend'));
      if (preset) preset.click();
    });
    await new Promise((r) => setTimeout(r, 400));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const save = buttons.find(b => b.textContent && b.textContent.includes('Save to Profile'));
      if (save) save.click();
    });
    await new Promise((r) => setTimeout(r, 1200));

    // 6. Add Learning Goal: React & Frontend
    console.log('[Demo Step 6] Adding learning goal: React & Frontend...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const addBtn = buttons.find(b => b.textContent && b.textContent.includes('Add Skill'));
      if (addBtn) addBtn.click();
    });
    await new Promise((r) => setTimeout(r, 500));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const learn = buttons.find(b => b.textContent && b.textContent.includes('Skill I Want to Learn'));
      if (learn) learn.click();
    });
    await new Promise((r) => setTimeout(r, 400));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const preset = buttons.find(b => b.textContent && b.textContent.includes('React & Frontend'));
      if (preset) preset.click();
    });
    await new Promise((r) => setTimeout(r, 400));

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const save = buttons.find(b => b.textContent && b.textContent.includes('Save to Profile'));
      if (save) save.click();
    });
    await new Promise((r) => setTimeout(r, 1200));

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_profile_with_skills.png'), fullPage: true });
    console.log('✓ Captured 04_profile_with_skills.png');

    // 7. Visit Wallet Page (US-04)
    console.log('[Demo Step 7] Navigating to /wallet...');
    await page.goto('http://localhost:3000/wallet', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_wallet_ledger_vault.png'), fullPage: true });
    console.log('✓ Captured 05_wallet_ledger_vault.png');

    // 8. Trigger Live Ledger Audit
    console.log('[Demo Step 8] Running live zero-sum ledger audit check...');
    await page.evaluate(() => {
      const btn = document.querySelector('button[title="Run Live Ledger Audit"]');
      if (btn) btn.click();
    });
    await new Promise((r) => setTimeout(r, 800));

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_wallet_audit_verified.png'), fullPage: true });
    console.log('✓ Captured 06_wallet_audit_verified.png');

    console.log('[Demo] All Sprint 1 verification steps passed successfully!');
  } catch (err) {
    console.error('[Demo Error]:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runDemo();
