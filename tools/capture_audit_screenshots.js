const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const WebSocket = require(path.join(__dirname, '../web/node_modules/ws'));

const OUT_DIR = path.join(__dirname, '../docs/final_audit/screenshots');
if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

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

function httpPost(url, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
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
    req.write(body);
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

  async captureScreenshot(filename) {
    const res = await this.send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    const filePath = path.join(OUT_DIR, filename);
    fs.writeFileSync(filePath, buffer);
    console.log(`Saved screenshot: ${filename} (${buffer.length} bytes)`);
  }

  close() {
    if (this.ws) this.ws.close();
  }
}

async function main() {
  console.log('Fetching scenario data from FastAPI...');
  const scenarios = ['CLEAN', 'BLOCK', 'UNVERIFIED', 'HIGH'];
  const scenarioData = {};
  for (const s of scenarios) {
    const detail = await httpGet(`http://127.0.0.1:8000/api/scenarios/${s}`);
    const triageReq = {
      patient: detail.patient,
      include_complaint_in_llm: false,
      llm_profile: 'COMPLIANT',
    };
    const triageRes = await httpPost('http://127.0.0.1:8000/api/triage', JSON.stringify(triageReq));
    scenarioData[s] = { req: triageReq, res: triageRes };
  }

  console.log('Launching headless Chrome...');
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
  ]);

  await wait(2000);

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

    async function navigateAndRender(url, delay = 800) {
      await cdp.send('Page.navigate', { url });
      await wait(delay);
    }

    async function setTheme(isDark) {
      await cdp.eval(`
        localStorage.setItem('triagerag-theme', '${isDark ? 'dark' : 'light'}');
        localStorage.setItem('theme', '${isDark ? 'dark' : 'light'}');
        if (${isDark}) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      `);
      await wait(200);
    }

    async function setScenarioState(scenarioKey) {
      const data = scenarioData[scenarioKey];
      await cdp.eval(`
        sessionStorage.setItem('triagerag_patient_request', ${JSON.stringify(JSON.stringify(data.req))});
        sessionStorage.setItem('triagerag_triage_result', ${JSON.stringify(JSON.stringify(data.res))});
      `);
    }

    // --- 1. Desktop Viewport (1280x850) ---
    await setViewport(1280, 850, false);
    await setTheme(false);

    // 1. Patient Details — light mode
    await navigateAndRender('http://localhost:5173/intake');
    await setTheme(false);
    await wait(400);
    await cdp.captureScreenshot('01_patient_details_light.png');

    // 2. Care Steps — normal verified result (CLEAN scenario)
    await setScenarioState('CLEAN');
    await navigateAndRender('http://localhost:5173/report');
    await wait(400);
    await cdp.captureScreenshot('02_care_steps_verified_normal.png');

    // 3. Care Steps — BLOCK result (BLOCK scenario)
    await setScenarioState('BLOCK');
    await navigateAndRender('http://localhost:5173/report');
    await wait(400);
    await cdp.captureScreenshot('03_care_steps_block_result.png');

    // 4. Care Steps — UNVERIFIED result (UNVERIFIED scenario)
    await setScenarioState('UNVERIFIED');
    await navigateAndRender('http://localhost:5173/report');
    await wait(400);
    await cdp.captureScreenshot('04_care_steps_unverified_result.png');

    // 5. Safety Rules
    await navigateAndRender('http://localhost:5173/rules', 1000);
    await wait(500);
    await cdp.captureScreenshot('05_safety_rules.png');

    // 6. Care Guides
    await navigateAndRender('http://localhost:5173/protocols', 1000);
    await wait(500);
    await cdp.captureScreenshot('06_care_guides.png');

    // 7. Sample Data
    await navigateAndRender('http://localhost:5173/sample-data', 800);
    await wait(400);
    await cdp.captureScreenshot('07_sample_data.png');

    // 8. Complete application — dark mode overview
    await setTheme(true);
    await navigateAndRender('http://localhost:5173/intake', 800);
    await setTheme(true);
    await wait(400);
    await cdp.captureScreenshot('08_dark_mode_overview.png');

    // --- 2. Mobile Viewport (390x844) ---
    await setViewport(390, 844, true);
    await setTheme(false);

    // 9. Mobile Patient Details (390px)
    await navigateAndRender('http://localhost:5173/intake', 800);
    await wait(400);
    await cdp.captureScreenshot('09_mobile_patient_details.png');

    // 10. Mobile Care Steps (390px)
    await setScenarioState('CLEAN');
    await navigateAndRender('http://localhost:5173/report', 800);
    await wait(400);
    await cdp.captureScreenshot('10_mobile_care_steps.png');

    // 11. Mobile navigation (390px)
    await navigateAndRender('http://localhost:5173/intake', 600);
    await cdp.eval(`
      const btn = document.querySelector('button[aria-label="Toggle navigation menu"]');
      if (btn) btn.click();
    `);
    await wait(500);
    await cdp.captureScreenshot('11_mobile_navigation.png');

    cdp.close();
    console.log('All 11 screenshots successfully captured!');
  } finally {
    chromeProc.kill('SIGKILL');
  }
}

main().catch((err) => {
  console.error('Screenshot capture failed:', err);
  process.exit(1);
});
