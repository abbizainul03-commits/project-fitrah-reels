// Renders the PNG cards (and the default background loop) from templates/card.html.
// Works with either Puppeteer (Colab: `npm install puppeteer`) or Playwright.
//
//   node render_cards.js stills <jobs.json>
//       jobs.json = [{ "out": "path.png", "card": { type: "ayah"|"intro"|"overlay", ... } }, ...]
//   node render_cards.js bgframes <outDir> <seconds> <fps>
const fs = require('fs');
const path = require('path');

const TEMPLATE = 'file://' + path.join(__dirname, 'templates', 'card.html');

async function launch() {
  try {
    const puppeteer = require('puppeteer');
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--force-color-profile=srgb'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
    return { browser, page };
  } catch (e) {
    const { chromium } = require('playwright');
    const browser = await chromium.launch({ args: ['--force-color-profile=srgb'] });
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    return { browser, page };
  }
}

(async () => {
  const [mode, a, b, c] = process.argv.slice(2);
  const { browser, page } = await launch();
  await page.goto(TEMPLATE, { waitUntil: 'load' });

  if (mode === 'stills') {
    const jobs = JSON.parse(fs.readFileSync(a, 'utf8'));
    for (const job of jobs) {
      await page.evaluate(card => window.renderCard(card), job.card);
      await page.screenshot({ path: job.out, omitBackground: true });
    }
    console.log(`Rendered ${jobs.length} cards`);
  } else if (mode === 'bgframes') {
    const outDir = a, seconds = Number(b), fps = Number(c);
    fs.mkdirSync(outDir, { recursive: true });
    await page.evaluate(() => { document.querySelectorAll('.stage').forEach(s => s.classList.remove('on')); document.getElementById('bg').classList.add('on'); });
    const total = Math.round(seconds * fps);
    for (let i = 0; i < total; i++) {
      // Freeze all CSS animations at an exact time: deterministic, seamless loop.
      await page.evaluate(ms => document.getAnimations().forEach(an => { an.pause(); an.currentTime = ms; }), (i / fps) * 1000);
      await page.screenshot({ path: path.join(outDir, `f_${String(i).padStart(5, '0')}.png`) });
    }
    console.log(`Rendered ${total} background frames`);
  } else {
    console.error('usage: node render_cards.js stills <jobs.json> | bgframes <outDir> <seconds> <fps>');
    process.exitCode = 1;
  }
  await browser.close();
})();
