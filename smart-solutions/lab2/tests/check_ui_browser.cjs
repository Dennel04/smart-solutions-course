/* Optional local browser regression: requires Playwright and Chromium.
 * Run from Lab 2: node tests/check_ui_browser.cjs
 * Set NODE_PATH / CHROMIUM_EXECUTABLE_PATH if using an external runtime.
 * All HTTP requests are intercepted; only synthetic fixtures are displayed.
 */
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const { existsSync, mkdirSync, mkdtempSync } = require('node:fs');
const { resolve, join } = require('node:path');
const { tmpdir } = require('node:os');
const assert = require('node:assert/strict');

const root = resolve(__dirname, '..');
const python = process.env.LAB2_PYTHON || join(root, '.venv/bin/python');
const screenshots = process.env.UI_SCREENSHOT_DIR || mkdtempSync(join(tmpdir(), 'lab2-language-review-'));
mkdirSync(screenshots, { recursive: true });
const fixtures = JSON.parse(execFileSync(python, ['-c', `
import json, tempfile
from pathlib import Path
from flask import render_template
from server.app import create_app
with tempfile.TemporaryDirectory() as directory:
    app = create_app({'TESTING': True, 'DATABASE_PATH': str(Path(directory) / 'preview.sqlite3'),
                     'USER_PASSWORD': 'synthetic-only', 'ATOM_API_KEY': 'synthetic-only'})
    jobs = []
    for i, status in enumerate(['queued', 'claimed', 'done', 'refused', 'expired']):
        kind = 'letter' if i % 2 == 0 else 'pick_place'
        jobs.append(dict(id='synthetic-job-' + str(i) + '-' + 'a' * 50, job=kind,
            arg={'letter': 'A'} if kind == 'letter' else {'routine': 'source_to_finished'},
            status=status, created_at='2030-01-01T12:00:0' + str(i) + '.123456Z',
            result={'source': 'synthetic_preview_only'} if status == 'done' else None,
            reason='synthetic_refusal_' * 6 if status == 'refused' else ('ttl_expired' if status == 'expired' else None)))
    with app.test_request_context():
        def render(state='offline', error=None, rows=jobs):
            return render_template('index.html', jobs=rows, default_ttl=60, error=error,
                atom={'status': state, 'last_seen': '2030-01-01T11:59:00.123456Z'})
        pages = {'/': render(), '/online': render('online'), '/stale': render('stale'),
            '/empty': render(rows=[]), '/error': render(error='ttl_seconds must be between 1 and 3600.'),
            '/hostile': render(error='<img src=x onerror=alert(1)> error.letter'),
            '/unauthorized-preview': render_template('unauthorized.html')}
        banner = '<aside style="padding:10px 16px;background:#fff1db;color:#704800;text-align:center;font:600 13px system-ui">SÜNTEETILINE / СИНТЕТИЧЕСКИЙ / SYNTHETIC PREVIEW · NOT HARDWARE RESULTS</aside>'
        print(json.dumps({path: html.replace('<body>', '<body>' + banner) for path, html in pages.items()}))
`], { cwd: root, encoding: 'utf8' }));
const origin = 'http://127.0.0.1:58291';
const messages = JSON.parse(fixtures['/'].match(/const messages = ([\s\S]*?);\n  const own/)[1]);
let count = 0;

async function preview(browser, options = {}, saved = {}, blocked = false) {
  const context = await browser.newContext({ viewport: { width: 375, height: 1000 }, colorScheme: 'light', ...options });
  await context.addInitScript(({ saved, blocked }) => {
    if (blocked) Object.defineProperty(window, 'localStorage', {
      get() { throw new DOMException('Synthetic blocked storage', 'SecurityError'); }
    });
    else for (const [key, value] of Object.entries(saved)) {
      if (sessionStorage.getItem('fixture-initialized') !== 'yes') localStorage.setItem(key, value);
    }
    sessionStorage.setItem('fixture-initialized', 'yes');
  }, { saved, blocked });
  const page = await context.newPage();
  const errors = [], requests = [];
  let posted;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const request = route.request();
    assert(request.url().startsWith(origin + '/'), 'No external network requests allowed');
    const path = new URL(request.url()).pathname;
    requests.push(request.method() + ' ' + path);
    if (request.method() === 'POST') {
      posted = Object.fromEntries(new URLSearchParams(request.postData()));
      return route.fulfill({ contentType: 'text/html', body: '<p>Synthetic form payload captured.</p>' });
    }
    assert(path in fixtures, 'Unexpected fixture path: ' + path);
    // Preview the real 401 template without a browser-native auth dialog.
    // Flask tests separately check the actual HTTP 401 and Basic challenge.
    return route.fulfill({ contentType: 'text/html', body: fixtures[path] });
  });
  return { context, page, errors, requests, get posted() { return posted; } };
}

async function checkLanguage(page, lang) {
  await page.waitForFunction(lang => document.documentElement.lang === lang, lang);
  assert.equal(await page.locator('#ui-language').inputValue(), lang);
  const texts = await page.locator('[data-i18n]').evaluateAll(nodes => nodes.map(node => ({
    key: node.dataset.i18n, text: node.textContent, max: node.dataset.i18nMax || ''
  })));
  for (const node of texts) assert.equal(node.text, messages[lang][node.key].replace('{max}', node.max), node.key);
  const dark = await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme === 'dark');
  const label = messages[lang][dark ? 'theme.light' : 'theme.dark'];
  assert.equal(await page.locator('#theme-toggle').getAttribute('aria-label'), label);
  assert.equal(await page.locator('.theme-label').textContent(), label);
  assert.equal(await page.locator('#theme-toggle').getAttribute('aria-pressed'), null);
}

async function checkLayout(page) {
  const metrics = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth,
    clipped: [...document.querySelectorAll('td,code,time,h1,p')].filter(node =>
      node.scrollWidth > node.clientWidth + 1 && getComputedStyle(node).display !== 'inline').map(node => node.tagName),
    smallControls: [...document.querySelectorAll('input,select,button,a.button-link')].filter(node =>
      node.getClientRects().length && node.getBoundingClientRect().height < 44).map(node => node.id),
    clippedOptions: [...document.querySelectorAll('select')].filter(node => {
      if (!node.getClientRects().length) return false;
      const css = getComputedStyle(node);
      const canvas = document.createElement('canvas').getContext('2d');
      canvas.font = css.font;
      const available = node.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight) - 24;
      return canvas.measureText(node.selectedOptions[0].textContent).width > available;
    }).map(node => node.id)
  }));
  assert.equal(metrics.overflow, false);
  assert.deepEqual(metrics.clipped, []);
  assert.deepEqual(metrics.smallControls, []);
  assert.deepEqual(metrics.clippedOptions, []);
}

async function takeScreenshot(page, name) {
  await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => {
    window.scrollTo(0, 0);
    requestAnimationFrame(resolve);
  })));
  await page.screenshot({ path: join(screenshots, name + '.png'), fullPage: true });
}

(async () => {
  const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({ headless: true, executablePath:
    process.env.CHROMIUM_EXECUTABLE_PATH || (existsSync(macChrome) ? macChrome : undefined) });
  try {
    for (const width of [375, 768, 1440]) for (const theme of ['light', 'dark']) for (const lang of ['et', 'ru', 'en']) {
      const sample = await preview(browser, { viewport: { width, height: 1000 }, colorScheme: theme });
      const { page, context } = sample;
      await page.goto(origin + '/');
      await checkLanguage(page, 'et');
      await page.locator('#letter').fill('B');
      await page.locator('#ttl-seconds').fill('45');
      await page.locator('#job').selectOption('pick_place');
      const machine = await page.locator('code:not([data-i18n]), time').allTextContents();
      const initialRequests = sample.requests.length;
      assert.equal(initialRequests, 1, 'Translations must not require another request');
      await page.locator('#ui-language').focus();
      assert(await page.locator('#ui-language').evaluate(node => node.matches(':focus-visible')));
      await page.locator('#ui-language').selectOption(lang);
      await checkLanguage(page, lang);
      await checkLayout(page);
      assert.equal(await page.locator('#letter').inputValue(), 'B');
      assert.equal(await page.locator('#ttl-seconds').inputValue(), '45');
      assert.equal(await page.locator('#job').inputValue(), 'pick_place');
      assert.deepEqual(await page.locator('code:not([data-i18n]), time').allTextContents(), machine);
      const toggle = page.locator('#theme-toggle');
      await toggle.focus(); await page.keyboard.press('Space'); await checkLanguage(page, lang);
      await page.keyboard.press('Enter'); await checkLanguage(page, lang);
      assert.equal(sample.requests.length, initialRequests, 'Switching language/theme must not send requests');
      const shot = { '1440-light-et': 'light-et-desktop', '375-light-ru': 'light-ru-mobile',
        '375-light-en': 'light-en-mobile', '1440-dark-ru': 'dark-ru-desktop', '375-dark-en': 'dark-en-mobile' }[width + '-' + theme + '-' + lang];
      if (shot) await takeScreenshot(page, shot);
      await page.reload(); await checkLanguage(page, lang);
      await page.goto(origin + '/unauthorized-preview'); await checkLanguage(page, lang); await checkLayout(page);
      assert.equal(await page.getByRole('heading', { name: messages[lang]['auth.heading'] }).count(), 1);
      if (width === 375 && ((lang === 'ru' && theme === 'light') || (lang === 'en' && theme === 'dark'))) {
        await takeScreenshot(page, '401-' + lang);
      }
      assert.deepEqual(sample.errors, []);
      await context.close(); count++;
    }
    for (const path of ['/online', '/stale', '/empty', '/error', '/hostile']) for (const lang of ['et', 'ru', 'en']) {
      const sample = await preview(browser, {}, { 'lab2-language': lang });
      await sample.page.goto(origin + path); await checkLanguage(sample.page, lang); await checkLayout(sample.page);
      assert.equal(await sample.page.locator('img').count(), 0);
      if (path === '/hostile') assert((await sample.page.getByRole('alert').textContent()).includes('<img src=x onerror=alert(1)>'));
      assert.deepEqual(sample.errors, []); await sample.context.close(); count++;
    }
    for (const blocked of [false, true]) {
      const sample = await preview(browser, { colorScheme: 'dark' }, { 'lab2-language': '__proto__' }, blocked);
      await sample.page.goto(origin + '/'); await checkLanguage(sample.page, 'et');
      await sample.page.locator('#ui-language').selectOption('ru'); await checkLanguage(sample.page, 'ru');
      await sample.page.locator('#theme-toggle').click(); await checkLanguage(sample.page, 'ru');
      await sample.page.reload(); await checkLanguage(sample.page, blocked ? 'et' : 'ru');
      assert.deepEqual(sample.errors, []); await sample.context.close(); count++;
    }
    for (const lang of ['et', 'ru', 'en']) for (const job of ['letter', 'pick_place']) {
      const sample = await preview(browser, {}, { 'lab2-language': lang });
      await sample.page.goto(origin + '/'); await checkLanguage(sample.page, lang);
      await sample.page.locator('#job').selectOption(job);
      if (job === 'letter') await sample.page.locator('#letter').fill('B');
      await sample.page.getByRole('button', { name: messages[lang]['form.submit'], exact: true }).click();
      await sample.page.waitForURL('**/jobs');
      assert.deepEqual(sample.posted, job === 'letter' ? { job, letter: 'B', ttl_seconds: '60' } :
        { job, routine: 'source_to_finished', ttl_seconds: '60' });
      await sample.context.close(); count++;
    }
    for (const colorScheme of ['light', 'dark']) {
      const sample = await preview(browser, { javaScriptEnabled: false, colorScheme });
      await sample.page.goto(origin + '/'); await checkLayout(sample.page);
      assert.equal(await sample.page.locator('html').getAttribute('lang'), 'et');
      assert.equal(await sample.page.locator('#language-control').isVisible(), false);
      assert.equal(await sample.page.locator('#theme-toggle').isVisible(), false);
      assert.equal(await sample.page.locator('#routine').isVisible(), true);
      await sample.page.locator('#job').selectOption('pick_place');
      await sample.page.getByRole('button', { name: 'Lisa järjekorda' }).click();
      await sample.page.waitForURL('**/jobs');
      assert.deepEqual(sample.posted, { job: 'pick_place', letter: '', routine: 'source_to_finished', ttl_seconds: '60' });
      await sample.context.close(); count++;
    }
    console.log(count + ' Chromium scenarios passed. Synthetic screenshots: ' + screenshots);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
