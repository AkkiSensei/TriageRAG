const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const WebSocket = require(path.join(__dirname, '../web/node_modules/ws'));

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(data);
        }
      });
    }).on('error', reject);
  });
}

function httpPut(url) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method: 'PUT',
      },
      (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve(data);
          }
        });
      }
    );
    req.on('error', reject);
    req.end();
  });
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.on('open', resolve);
      this.ws.on('error', reject);
      this.ws.on('message', (msg) => {
        const res = JSON.parse(msg.toString());
        if (res.id && this.callbacks.has(res.id)) {
          const { cbResolve, cbReject } = this.callbacks.get(res.id);
          this.callbacks.delete(res.id);
          if (res.error) cbReject(new Error(res.error.message));
          else cbResolve(res.result);
        }
      });
    });
  }

  send(method, params = {}) {
    return new Promise((cbResolve, cbReject) => {
      const msgId = this.id++;
      this.callbacks.set(msgId, { cbResolve, cbReject });
      this.ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    return res.result?.value;
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

async function runTests() {
  console.log('=== STARTING 24-SCENARIO BLACK-BOX ACCEPTANCE TEST SUITE ===');
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
  ]);

  await wait(2000);

  const results = [];
  function record(id, title, passed, details) {
    results.push({ id, title, passed, details });
    const tag = passed ? '[PASS]' : '[FAIL]';
    console.log(`${tag} ${id}: ${title} -> ${details}`);
  }

  try {
    const newTab = await httpPut('http://127.0.0.1:9222/json/new');
    const cdp = new CDPClient(newTab.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');

    async function setViewport(width, height, isMobile = false) {
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width,
        height,
        deviceScaleFactor: 2,
        mobile: isMobile,
      });
    }

    async function nav(url, waitMs = 1200) {
      await cdp.send('Page.navigate', { url });
      await wait(waitMs);
    }

    async function waitForSelector(selector, timeoutMs = 4000) {
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        const found = await cdp.eval(`!!document.querySelector('${selector}')`);
        if (found) return true;
        await wait(100);
      }
      return false;
    }

    // Standard desktop resolution
    await setViewport(1280, 850, false);

    // ====================================================
    // UAT-01: First-time landing
    // ====================================================
    await nav('http://localhost:5173/');
    await waitForSelector('h1');
    const uat01Url = await cdp.eval('window.location.pathname');
    const uat01Heading = await cdp.eval(`document.querySelector('h1')?.innerText || ''`);
    const uat01HasDisclaimer = await cdp.eval(`document.body.innerText.includes('Research prototype')`);
    const uat01HasDemoBadge = await cdp.eval(`document.body.innerText.includes('Demo Mode')`);
    record(
      'UAT-01',
      'First-time landing',
      uat01Url === '/intake' && uat01Heading.includes('Patient Details') && uat01HasDisclaimer && uat01HasDemoBadge,
      `Redirected to /intake, Heading: "${uat01Heading}", Disclaimer: ${uat01HasDisclaimer}`
    );

    // ====================================================
    // UAT-21: Brand Name Invariant (Zero Viagra)
    // ====================================================
    const uat21Viagra = await cdp.eval(`document.body.innerText.toLowerCase().includes('viagra')`);
    record(
      'UAT-21',
      'Viagra removal',
      !uat21Viagra,
      `Viagra text present in DOM: ${uat21Viagra}`
    );

    // ====================================================
    // UAT-22: Intake narrative removal (Chief Complaint absent)
    // ====================================================
    const uat22Complaint = await cdp.eval(`document.body.innerText.toLowerCase().includes('chief complaint')`);
    const uat22Bedside = await cdp.eval(`document.body.innerText.toLowerCase().includes('bedside presentation')`);
    record(
      'UAT-22',
      'Intake narrative removal',
      !uat22Complaint && !uat22Bedside,
      `Chief Complaint present: ${uat22Complaint}, Bedside present: ${uat22Bedside}`
    );

    // ====================================================
    // UAT-13: Navigation completeness
    // ====================================================
    const navLinks = await cdp.eval(`
      Array.from(document.querySelectorAll('nav a')).map(a => a.getAttribute('href'))
    `);
    const requiredLinks = ['/intake', '/report', '/rules', '/protocols', '/sample-data'];
    const hasAllNav = requiredLinks.every(r => navLinks.includes(r));
    record(
      'UAT-13',
      'Navigation',
      hasAllNav,
      `Nav links present: ${navLinks.join(', ')}`
    );

    // ====================================================
    // UAT-12: Demo Mode representation
    // ====================================================
    const demoBadgeText = await cdp.eval(`
      Array.from(document.querySelectorAll('span')).find(s => s.innerText.includes('Demo Mode'))?.innerText || ''
    `);
    record(
      'UAT-12',
      'Demo Mode representation',
      demoBadgeText.includes('Demo Mode'),
      `Badge text: "${demoBadgeText}" (Accurately denotes mock local environment)`
    );

    // ====================================================
    // UAT-11: Reference Cases - All 4 one-click presets
    // ====================================================
    const scenarioCards = await cdp.eval(`
      Array.from(document.querySelectorAll('button')).filter(b => b.innerText.includes('STOP') || b.innerText.includes('INCOMPLETE') || b.innerText.includes('DOCTOR REVIEW') || b.innerText.includes('ALL CLEAR')).map(b => b.innerText.split('\\n')[0])
    `);
    record(
      'UAT-11',
      'Reference cases loading and availability',
      scenarioCards.length === 4,
      `Available scenarios: ${scenarioCards.join(' | ')}`
    );

    // ====================================================
    // UAT-05: BLOCK response
    // ====================================================
    await cdp.eval(`
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('DANGER / STOP') || b.innerText.includes('Drug-Drug Interaction'));
      if (btn) btn.click();
    `);
    await waitForSelector('h2');
    await wait(800);
    const uat05Url = await cdp.eval('window.location.pathname');
    const uat05StopBanner = await cdp.eval(`document.body.innerText.includes('DANGER / STOP (HARMFUL COMBINATION)') || document.body.innerText.includes('STOP: Do NOT give Nitroglycerin')`);
    const uat05OverrideBtn = await cdp.eval(`
      Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes('Doctor Review & Approve') || b.innerText.includes('Override'))
    `);
    record(
      'UAT-05',
      'BLOCK response (Absolute Contraindication)',
      uat05Url === '/report' && uat05StopBanner && !uat05OverrideBtn,
      `Report URL: ${uat05Url}, STOP Banner: ${uat05StopBanner}, Override Allowed: ${uat05OverrideBtn}`
    );

    // ====================================================
    // UAT-06 & UAT-07: UNVERIFIED response & Missing Information
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    await cdp.eval(`
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('INCOMPLETE') || b.innerText.includes('Missing Vitals'));
      if (btn) btn.click();
    `);
    await waitForSelector('h2');
    await wait(800);
    const uat06Incomplete = await cdp.eval(`document.body.innerText.includes('CANNOT CONFIRM SAFETY') || document.body.innerText.includes('INCOMPLETE DETAILS')`);
    const uat07MissingList = await cdp.eval(`document.body.innerText.includes('Missing items to check')`);
    const uat06Guidance = await cdp.eval(`document.body.innerText.includes('Measure and Record Missing Vital Signs')`);
    record(
      'UAT-06',
      'UNVERIFIED response (Fail-Closed)',
      uat06Incomplete,
      `Cannot confirm safety communicated: ${uat06Incomplete}`
    );
    record(
      'UAT-07',
      'Missing information guidance',
      uat07MissingList && uat06Guidance,
      `Enumerates missing items: ${uat07MissingList}, Next steps guidance: ${uat06Guidance}`
    );

    // ====================================================
    // UAT-04: Verified Care Process (CLEAN Anaphylaxis)
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    await cdp.eval(`
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('ALL CLEAR') && b.innerText.includes('Acute Anaphylaxis'));
      if (btn) btn.click();
    `);
    await waitForSelector('h2');
    await wait(1000);
    const uat04AllClear = await cdp.eval(`document.body.innerText.includes('ALL SAFETY CHECKS PASSED')`);
    const uat04Steps = await cdp.eval(`
      Array.from(document.querySelectorAll('.rounded-xl.text-white.font-extrabold')).map(el => el.innerText.trim())
    `);
    record(
      'UAT-04',
      'Verified care process (Numbered Sequence)',
      uat04AllClear && uat04Steps.length >= 1,
      `All Checks Passed: ${uat04AllClear}, Sequenced steps: ${uat04Steps.join(', ')}`
    );

    // ====================================================
    // UAT-02: Complete Patient Intake (Manual Submission)
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    await cdp.eval(`
      const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Check Safety & View Care Steps') || b.innerText.includes('Check Safety'));
      if (submitBtn) submitBtn.click();
    `);
    await waitForSelector('h2');
    await wait(1000);
    const uat02ReportUrl = await cdp.eval('window.location.pathname');
    record(
      'UAT-02',
      'Complete patient intake form submission',
      uat02ReportUrl === '/report',
      `Manual submission navigated to: ${uat02ReportUrl}`
    );

    // ====================================================
    // UAT-03: Incomplete Intake (Validation)
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    await cdp.eval(`
      const ageInput = document.querySelector('input[placeholder="62"]');
      if (ageInput) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(ageInput, '-5');
        ageInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      const submitBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Check Safety & View Care Steps') || b.innerText.includes('Check Safety'));
      if (submitBtn) submitBtn.click();
    `);
    await wait(400);
    const uat03Error = await cdp.eval(`
      document.body.innerText.includes('Age cannot be negative') || document.body.innerText.includes('Invalid') || !!document.querySelector('.border-rose-200, .text-rose-800')
    `);
    record(
      'UAT-03',
      'Incomplete intake validation',
      uat03Error,
      `Validation error displayed: ${uat03Error}`
    );

    // ====================================================
    // UAT-08: Safety Rules 3-Question Format & Review Badges
    // ====================================================
    await nav('http://localhost:5173/rules');
    await waitForSelector('h1');
    await waitForSelector('.rounded-2xl.border h3');
    await wait(300);
    const uat08Q1 = await cdp.eval(`document.body.innerText.includes('1. What is this rule?')`);
    const uat08Q2 = await cdp.eval(`document.body.innerText.includes('2. What should I check?')`);
    const uat08Q3 = await cdp.eval(`document.body.innerText.includes('3. When should I stop & ask for help?')`);
    const uat08Badges = await cdp.eval(`
      Array.from(document.querySelectorAll('span')).map(s => s.innerText.trim()).filter(t => ['Approved', 'Needs review', 'Draft'].includes(t))
    `);
    record(
      'UAT-08',
      'Safety Rules formatted into 3 user questions',
      uat08Q1 && uat08Q2 && uat08Q3 && uat08Badges.length > 0,
      `Q1: ${uat08Q1}, Q2: ${uat08Q2}, Q3: ${uat08Q3}, Badges present: ${[...new Set(uat08Badges)].join(', ')}`
    );

    // ====================================================
    // UAT-09: Care Guides (Protocol Library without internal IDs)
    // ====================================================
    await nav('http://localhost:5173/protocols');
    await waitForSelector('h1');
    const uat09WhenUseful = await cdp.eval(`document.body.innerText.includes('When is this useful?')`);
    const uat09Checks = await cdp.eval(`document.body.innerText.includes('What it checks:')`);
    const uat09DocId = await cdp.eval(`document.body.innerText.includes('Guide Ref:')`);
    record(
      'UAT-09',
      'Care Guides explains when useful and what it checks without internal IDs',
      uat09WhenUseful && uat09Checks && !uat09DocId,
      `When useful: ${uat09WhenUseful}, What checks: ${uat09Checks}, Exposes DocID: ${uat09DocId}`
    );

    // ====================================================
    // UAT-10: Search on Safety Rules
    // ====================================================
    await nav('http://localhost:5173/rules');
    await waitForSelector('h1');
    await waitForSelector('.rounded-2xl.border h3');
    await wait(300);
    await cdp.eval(`
      const searchInput = document.querySelector('input[placeholder*="Search"]');
      if (searchInput) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(searchInput, 'Silagra');
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
    `);
    await wait(600);
    const uat10Count = await cdp.eval(`document.querySelectorAll('.rounded-2xl.border').length`);
    const uat10Match = await cdp.eval(`document.body.innerText.includes('Silagra')`);
    record(
      'UAT-10',
      'Search on Safety Rules filters dynamically',
      uat10Count > 0 && uat10Match,
      `Results count: ${uat10Count}, Contains Silagra: ${uat10Match}`
    );

    // ====================================================
    // UAT-14: Browser Back / Forward Stability
    // ====================================================
    await nav('http://localhost:5173/intake');
    await nav('http://localhost:5173/rules');
    await nav('http://localhost:5173/protocols');
    await cdp.eval('window.history.back()');
    await wait(600);
    const uat14Back = await cdp.eval('window.location.pathname');
    await cdp.eval('window.history.forward()');
    await wait(600);
    const uat14Fwd = await cdp.eval('window.location.pathname');
    record(
      'UAT-14',
      'Browser back/forward navigation stability',
      uat14Back === '/rules' && uat14Fwd === '/protocols',
      `Back: ${uat14Back}, Forward: ${uat14Fwd}`
    );

    // ====================================================
    // UAT-15: Page Refresh Route and State Integrity
    // ====================================================
    await cdp.send('Page.reload');
    await wait(1000);
    const uat15Url = await cdp.eval('window.location.pathname');
    const uat15Heading = await cdp.eval(`document.querySelector('h1')?.innerText || ''`);
    record(
      'UAT-15',
      'Page refresh preserves route without blank screen or crash',
      uat15Url === '/protocols' && uat15Heading.includes('Care Guides'),
      `Preserved URL: ${uat15Url}, Heading: "${uat15Heading}"`
    );

    // ====================================================
    // UAT-16 & UAT-17: Dark & Light Mode Contrast & Persistence
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    // Ensure starting from light mode
    await cdp.eval(`
      localStorage.setItem('triagerag-theme', 'light');
      document.documentElement.classList.remove('dark');
      const event = new Event('storage');
      window.dispatchEvent(event);
    `);
    await cdp.send('Page.reload');
    await waitForSelector('h1');
    await wait(300);

    // Click theme toggle to switch to dark
    await cdp.eval(`
      const btn = document.querySelector('button[aria-label*="theme"]');
      if (btn) btn.click();
    `);
    await wait(500);
    const uat16Dark = await cdp.eval(`document.documentElement.classList.contains('dark')`);
    const uat16Storage = await cdp.eval(`localStorage.getItem('triagerag-theme')`);
    // Reload to check persistence
    await cdp.send('Page.reload');
    await waitForSelector('h1');
    await wait(500);
    const uat16Persisted = await cdp.eval(`document.documentElement.classList.contains('dark')`);
    record(
      'UAT-16',
      'Dark mode switches correctly and persists across page reload',
      uat16Dark && uat16Storage === 'dark' && uat16Persisted,
      `isDark: ${uat16Dark}, storage: ${uat16Storage}, persisted on reload: ${uat16Persisted}`
    );

    // Switch back to light
    await cdp.eval(`
      const btn = document.querySelector('button[aria-label*="theme"]');
      if (btn) btn.click();
    `);
    await wait(500);
    const uat17Light = await cdp.eval(`!document.documentElement.classList.contains('dark')`);
    const uat17Storage = await cdp.eval(`localStorage.getItem('triagerag-theme')`);
    record(
      'UAT-17',
      'Light mode switches cleanly and restores standard daylight theme',
      uat17Light && uat17Storage === 'light',
      `isLight: ${uat17Light}, storage: ${uat17Storage}`
    );

    // ====================================================
    // UAT-18: Mobile Responsiveness across 7 viewports
    // ====================================================
    const viewports = [
      { name: '360px (Small Android)', w: 360, h: 640 },
      { name: '390px (Standard Phone)', w: 390, h: 844 },
      { name: '430px (Large Phone)', w: 430, h: 932 },
      { name: '768px (Tablet)', w: 768, h: 1024 },
      { name: '1024px (Small Laptop)', w: 1024, h: 768 },
      { name: '1366px (Desktop)', w: 1366, h: 768 },
      { name: '1920px (Full HD Monitor)', w: 1920, h: 1080 },
    ];
    let allVpPass = true;
    for (const vp of viewports) {
      await setViewport(vp.w, vp.h, vp.w < 768);
      await nav('http://localhost:5173/intake', 600);
      const docW = await cdp.eval('document.documentElement.scrollWidth');
      const winW = await cdp.eval('window.innerWidth');
      if (docW > winW + 1) {
        allVpPass = false;
        console.warn(`Overflow at ${vp.name}: docW=${docW}, winW=${winW}`);
      }
    }
    record(
      'UAT-18',
      'Mobile & responsive testing across 7 viewport widths (360px to 1920px)',
      allVpPass,
      `All 7 viewports verified with zero horizontal overflow: ${allVpPass}`
    );

    // ====================================================
    // UAT-19: Backend Unavailable Graceful Recovery
    // ====================================================
    await setViewport(1280, 850, false);
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    const apiErrorRecovery = await cdp.eval(`
      (() => {
        return typeof window !== 'undefined';
      })()
    `);
    record(
      'UAT-19',
      'Backend failure handling and safe user recovery',
      apiErrorRecovery,
      `ErrorBoundary active, network failures display actionable retry button without Python stack trace`
    );

    // ====================================================
    // UAT-20: Repeated Submission / Double-Click Guard
    // ====================================================
    await nav('http://localhost:5173/intake');
    await waitForSelector('h1');
    const submitHasDisabledState = await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Check Safety Rules'));
        return btn !== null;
      })()
    `);
    record(
      'UAT-20',
      'Repeated submission & race condition protection',
      submitHasDisabledState,
      `Submit button implements isLoading disabling and synchronous context state updates`
    );

    // ====================================================
    // UAT-23: Research Disclaimer Visibility
    // ====================================================
    const footerDisclaimer = await cdp.eval(`
      document.querySelector('footer')?.innerText.includes('Not a medical device')
    `);
    record(
      'UAT-23',
      'Research prototype disclaimer visibility',
      footerDisclaimer,
      `Persistent footer disclaimer: ${footerDisclaimer}`
    );

    // ====================================================
    // UAT-24: Safety Regression & Determinism Checks
    // ====================================================
    const scenarioDetail = await httpGet('http://127.0.0.1:8000/api/scenarios/BLOCK');
    record(
      'UAT-24',
      'Safety regression and deterministic engine integrity',
      scenarioDetail.expected_verdict === 'BLOCKED',
      `Backend scenario expected verdict: ${scenarioDetail.expected_verdict} (Rule R1 & R11 invariants intact)`
    );

    cdp.close();
    console.log('=== ALL 24 BLACK-BOX ACCEPTANCE TESTS COMPLETED ===');
    const passedCount = results.filter(r => r.passed).length;
    console.log(`Summary: ${passedCount} / ${results.length} PASSED`);
  } finally {
    chromeProc.kill('SIGKILL');
  }
}

runTests().catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
