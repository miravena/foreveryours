// v6 (#304): the v2 capture (video/v2/capture/capture.mjs) with Dad SPEAKING. Every senior
// line is spoken input: the script clicks Record, the browser microphone plays one of our Dad
// WAVs (video/v6/dad_voice.py), the script clicks Stop and Send, and the Space's own speech
// recognition turns it into the "Dad said" line. Chromium's file-fed fake microphone restarts its
// file on every recording, so one file cannot carry two lines in one session; instead an init
// script answers the recorder's getUserMedia with a stream that plays the next queued WAV. The
// Space receives an ordinary microphone recording either way. Usage as v2, with DAD_DIR pointing
// at the rendered WAVs (default <out_dir>/../dad_v6).
//
// The v2 header follows.
//
// Record the demo video's picture from the LIVE hosted Space, one clip per shot.
//
// Every clip is a real browser session on https://elevenbaselab-foreveryours.hf.space:
// Playwright's recordVideo captures the page (1920x1080, deviceScaleFactor 1, 110% page
// zoom so "Dad was told" reads on a phone), and every audio file the Space serves for
// "Companion's reply" is saved from the network as it arrives, because a Playwright video
// has no sound track. Nothing on screen is mocked: the script types, clicks and waits.
//
// Usage (from the repo root):
//   PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs \
//   CHROME_PATH=/path/to/chrome-linux/chrome \
//   node video/v2/capture/capture.mjs <out_dir> <shot> [<candidate senior line>]
//
// Shots: fall (shots 1 and 2), appt (shots 3 and 4: the appointment memo saved, then the
// senior asks about appointments, same session; run it three times with SHOT_TAG=appt_t1..t3
// to check the reply), crisis (shot 5). memo and senior are the earlier shot 3/4 attempts. Shot 6 is a local terminal run (see README.md here).
// Per shot it writes <out_dir>/<shot>.webm (raw), <shot>.mp4 (trimmed to the moment the page
// is ready), <shot>.json (key moments in seconds of the mp4, texts verbatim) and
// <shot>_reply_*.{aac,wav,...} (the reply audio the Space served).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const SPACE = process.env.SPACE_URL || 'https://elevenbaselab-foreveryours.hf.space';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');

const FALL = "I fell down earlier and I'm scared.";
const MEMO = 'Dad loves jazz. His grandson is named Leo. Avoid talking about driving. Sarah is dropping off groceries at 4 PM.';
const LONELY = 'I feel lonely since my wife died.';
const CRISIS = 'I want to end my life.';
// Shots 3 and 4 (one session): a memo the pre-briefed sample household does not already hold,
// then a senior question only that memo answers.
const APPT_MEMO = 'Dad has a check-up with Dr. Tan on Thursday at 10 AM.';
// The first wording, 'Do I have any appointments this week?', passed 2 of 3 runs (the third
// answered "no appointments listed" with the memo saved), so the shot uses the doctor wording.
const APPT_ASK = "Do I have any doctor's appointments this week?";

// Page dressing for a phone-legible recording: 110% zoom, the floating hosting badge
// hidden, and a visible pointer (headless video has no cursor of its own).
const CSS = `
  html { zoom: 1.1; }
  #huggingface-space-header, .hf-badge, [class*="space-header"] { display: none !important; }
  select.mic-select { visibility: hidden !important; }
  #fy-cursor { position: fixed; z-index: 2147483647; width: 22px; height: 22px; margin: -11px 0 0 -11px;
    border-radius: 50%; background: rgba(30,30,30,.35); border: 2px solid #fff;
    box-shadow: 0 0 0 1px rgba(0,0,0,.5); pointer-events: none; transition: transform .12s; }
  #fy-cursor.down { transform: scale(.7); }
`;
const CURSOR_JS = `
  (() => {
    const c = document.createElement('div'); c.id = 'fy-cursor'; c.style.left = '-50px'; c.style.top = '-50px';
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', () => c.classList.add('down'), true);
    document.addEventListener('mouseup', () => c.classList.remove('down'), true);
    document.addEventListener('play', () => window.fyPlay && window.fyPlay(), true);
  })();
`;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const [outDir, shot, candidate] = process.argv.slice(2);
  if (!outDir || !shot) { console.error('usage: capture.mjs <out_dir> <shot> [line]'); process.exit(2); }
  fs.mkdirSync(outDir, { recursive: true });
  const tag = process.env.SHOT_TAG || shot;
  const rawDir = path.join(outDir, `_raw_${tag}`);
  fs.rmSync(rawDir, { recursive: true, force: true });

  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: ['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream'],
  });
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: { dir: rawDir, size: { width: 1920, height: 1080 } },
  });
  const t0 = Date.now();                       // video timeline starts with the page
  const page = await ctx.newPage();
  const sec = () => (Date.now() - t0) / 1000;
  const moments = {};
  const mark = (k) => { moments[k] = +sec().toFixed(2); console.log(`[${moments[k]}s] ${k}`); };

  // Every time an <audio> element starts playing (autoplay of the reply), mark it.
  const plays = [];
  await page.exposeFunction('fyPlay', () => { plays.push(+sec().toFixed(2)); console.log(`[${sec().toFixed(2)}s] audio play`); });

  // Save every audio body the Space serves (streamed sentence files or the playlist segments).
  const audio = [];
  page.on('response', async (res) => {
    const url = res.url();
    const ct = (res.headers()['content-type'] || '').toLowerCase();
    const isAudio = ct.startsWith('audio/') || /\.(wav|mp3|aac|ogg|flac|ts|m4a)(\?|$)/.test(url)
      || ct.includes('mpegurl') || /playlist\.m3u8/.test(url);
    if (!isAudio || !/\/(gradio_api|file=|stream)/.test(url)) return;
    const at = sec();
    const isList = /\.m3u8(\?|$)/.test(url);
    if (!isList && audio.some(a => a.url === url)) return;   // the player re-requests segments
    try {
      const body = await res.body();
      const ext = (url.split('?')[0].match(/\.([a-z0-9]{2,4})$/i) || [, (ct.split('/')[1] || 'bin')])[1];
      audio.push({ url, ct, at: +at.toFixed(2), bytes: body.length, body, ext });
    } catch (e) { /* redirects / aborted range requests carry no body */ }
  });

  // The microphone: each getUserMedia call while a WAV is queued gets a stream that plays it
  // once from the start (then silence); the queue is one-shot, so nothing else hears it.
  await page.exposeFunction('fyMicStart', () => { mark(`${micKey}_mic_audio_start`); });
  await page.addInitScript(() => {
    const md = navigator.mediaDevices;
    const orig = md.getUserMedia.bind(md);
    md.getUserMedia = async (c) => {
      const b64 = window.__fyNextWav;
      if (!c || !c.audio || !b64) return orig(c);
      window.__fyNextWav = null;
      const ctx = new AudioContext({ sampleRate: 48000 });
      const bytes = Uint8Array.from(atob(b64), ch => ch.charCodeAt(0));
      const buf = await ctx.decodeAudioData(bytes.buffer);
      const src = ctx.createBufferSource(); src.buffer = buf;
      const dst = ctx.createMediaStreamDestination(); src.connect(dst);
      await ctx.resume(); src.start(); window.fyMicStart && window.fyMicStart();
      return dst.stream;
    };
  });
  let micKey = 'mic';

  await page.goto(SPACE, { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(15000);
  await page.addStyleTag({ content: CSS });
  await page.evaluate(CURSOR_JS);
  // Wait until the session's caregiver panel has rendered (briefed memory listed).
  await page.getByText('Briefed memory').first().waitFor({ timeout: 60000 });
  await page.mouse.move(960, 540);
  await page.waitForTimeout(800);

  const senior = page.getByLabel('Type (as the senior)');
  const send = page.getByRole('button', { name: 'Send', exact: true });
  const memoBox = page.getByLabel('Write context memo');
  const saveMemo = page.getByRole('button', { name: 'Save Text Memo' });

  async function moveAndClick(loc, quick = false) {
    const b = await loc.boundingBox();
    const x = b.x + b.width / 2, y = b.y + b.height / 2;
    await page.mouse.move(x, y, { steps: quick ? 8 : 25 });
    await page.waitForTimeout(quick ? 120 : 400);
    await page.mouse.down(); await page.waitForTimeout(120); await page.mouse.up();
  }
  async function typeInto(loc, text) {
    await moveAndClick(loc);
    await loc.pressSequentially(text, { delay: 55 });
    await page.waitForTimeout(700);
  }
  // Scroll so the Senior/Caregiver headings sit at the top: both columns in one frame.
  async function frameSplit() {
    await page.evaluate(() => {
      const h = [...document.querySelectorAll('h2')].find(e => e.textContent.includes('Senior side'));
      if (h) window.scrollTo({ top: window.scrollY + h.getBoundingClientRect().top - 12, behavior: 'smooth' });
    });
    await page.waitForTimeout(1200);
  }
  const transcriptText = () => page.evaluate(() => {
    const el = [...document.querySelectorAll('.prose, .md, [data-testid="markdown"]')]
      .filter(e => /Companion replied|Dad said/.test(e.innerText)).pop();
    return el ? el.innerText : '';
  });
  const panelText = () => page.evaluate(() => {
    const el = [...document.querySelectorAll('.prose, .md, [data-testid="markdown"]')]
      .filter(e => e.innerText.includes('What ForeverYours has told you')).pop();
    return el ? el.innerText : '';
  });
  // The headless player only ever requests the first segment of the reply's HLS stream,
  // so once the reply has finished, fetch the complete playlist and every segment it lists
  // from inside the page (same session). The response listener above saves the bodies.
  // The stream is gone once the session ends, so this must run before the page closes.
  async function fetchAllSegments() {
    const dirs = [...new Set(audio.filter(a => /\.m3u8/.test(a.url)).map(a => a.url.split('?')[0]))];
    for (const list of dirs) {
      await page.evaluate(async (u) => {
        let txt = '';
        for (let i = 0; i < 30; i++) {           // wait for #EXT-X-ENDLIST (all sentences voiced)
          txt = await (await fetch(u, { cache: 'no-store' })).text();
          if (txt.includes('#EXT-X-ENDLIST')) break;
          await new Promise(r => setTimeout(r, 1000));
        }
        const base = u.replace(/[^/]+$/, '');
        for (const l of txt.split('\n')) if (l && !l.startsWith('#')) await (await fetch(base + l)).arrayBuffer();
      }, list);
    }
    await page.waitForTimeout(1500);
  }
  // A turn, spoken: queue Dad's WAV, click Record, let it play, click Stop, click Send, wait for
  // "Dad said" (what the Space heard) and for the reply text to finish streaming.
  const DAD_DIR = process.env.DAD_DIR || path.join(outDir, '..', 'dad_v6');
  const recordBtn = page.locator('button.record-button:visible').first();
  const stopBtn = page.locator('button.stop-button:visible').first();
  async function seniorTurn(line, key, wavName) {
    const wav = path.join(DAD_DIR, `${wavName}.wav`);
    const wavDur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
      '-of', 'csv=p=0', wav]).toString());
    await page.evaluate((b) => { window.__fyNextWav = b; }, fs.readFileSync(wav).toString('base64'));
    const before = await transcriptText();
    const told = async () => ((await panelText()).match(/Dad was told/g) || []).length;
    const toldBefore = await told();
    let flagged = false;
    micKey = key;
    await moveAndClick(recordBtn);
    mark(`${key}_record_clicked`);
    const recAt = Date.now();
    await stopBtn.waitFor({ timeout: 15000 });
    // Each WAV ends with 1.2 s of silence; stop about 0.5 s after the last word, and move
    // the pointer to Send at once, so the wait on screen is the Space's, not the script's.
    const sb = await stopBtn.boundingBox();
    await page.mouse.move(sb.x + sb.width / 2, sb.y + sb.height / 2, { steps: 15 });
    await page.waitForTimeout(Math.max(0, wavDur * 1000 - 700 - (Date.now() - recAt)));
    await moveAndClick(stopBtn, true);
    mark(`${key}_stop_clicked`);
    await page.getByRole('button', { name: 'Play', exact: true }).first().waitFor({ timeout: 15000 });
    await moveAndClick(send, true);
    mark(`${key}_send_clicked`);
    let last = '', stableSince = 0, seen = false, heard = false;
    for (let i = 0; i < 300; i++) {
      await page.waitForTimeout(250);
      if (!flagged && (await told()) > toldBefore) { flagged = true; mark(`${key}_flag_visible`); }
      const t = await transcriptText();
      if (t && t !== before && /Dad said/.test(t) && !heard) { heard = true; mark(`${key}_heard_visible`); }
      if (t && t !== before && t.includes('Companion replied')) {
        if (!seen) { seen = true; mark(`${key}_reply_text_visible`); }
        if (t !== last) { last = t; stableSince = Date.now(); }
        else if (Date.now() - stableSince > 5000) break;
      }
    }
    mark(`${key}_reply_text_complete`);
    if (!flagged && (await told()) > toldBefore) mark(`${key}_flag_visible`);
    await fetchAllSegments();
    const m = last.match(/Companion replied:\s*"([\s\S]*?)"\s*(\n|$)/);
    const h = last.match(/Dad said:\s*"([\s\S]*?)"/);
    dadTurns.push({ key, intended: line, source_wav: wav, wav_duration: +wavDur.toFixed(2), heard: h ? h[1].trim() : null });
    return { transcript: last, reply: m ? m[1].trim() : last, heard: h ? h[1].trim() : null };
  }
  const dadTurns = [];
  async function waitPanel(re, key, timeoutS = 60) {
    for (let i = 0; i < timeoutS * 2; i++) {
      if (re.test(await panelText())) { mark(key); return true; }
      await page.waitForTimeout(500);
    }
    console.log(`!! panel never matched ${re}`); return false;
  }
  async function scrollToMemo() {
    await page.evaluate(() => {
      const h = [...document.querySelectorAll('h3')].find(e => e.textContent.includes('Briefed memory'));
      if (h) window.scrollTo({ top: window.scrollY + h.getBoundingClientRect().top - 260, behavior: 'smooth' });
    });
    await page.waitForTimeout(1500);
  }

  // Sync flash: a magenta square in the bottom-right corner for 0.5 s. Its frame in the
  // video pins the page clock to the video clock (Playwright's video does not start at
  // newPage()); one flash at the start and one at the end also measures any drift.
  async function flash(key) {
    await page.evaluate(() => { const d = document.createElement('div'); d.id = 'fy-sync';
      d.style.cssText = 'position:fixed;right:0;bottom:0;width:32px;height:32px;background:#ff00ff;z-index:2147483647';
      document.body.appendChild(d); });
    mark(key);
    await page.waitForTimeout(500);
    await page.evaluate(() => document.getElementById('fy-sync')?.remove());
    await page.waitForTimeout(500);
  }

  const result = { shot, tag, space: SPACE, captured_at: new Date().toISOString() };
  await frameSplit();
  await flash('sync_start');
  mark('ready');

  if (shot === 'fall') {
    const r = await seniorTurn(FALL, 'fall', 'dad_fall');
    result.senior_text = FALL;
    if (!moments.fall_flag_visible) await waitPanel(/Dad was told/, 'fall_flag_visible');
    await page.waitForTimeout(3000);
    mark('hold_3s_end');
    await page.waitForTimeout(12000);           // shot 2: steady hold of the split screen
    mark('hold_end');
    result.reply = r.reply; result.transcript = r.transcript; result.panel = await panelText();
  } else if (shot === 'appt') {
    await page.evaluate(() => {
      window.fyToasts = [];
      new MutationObserver(() => {
        for (const e of document.querySelectorAll('.toast-body, [data-testid="toast-body"]')) {
          const t = e.innerText.trim();
          if (t && !window.fyToasts.includes(t)) window.fyToasts.push(t);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true });
    });
    await scrollToMemo();
    await typeInto(memoBox, APPT_MEMO);
    await moveAndClick(saveMemo);
    mark('memo_saved_clicked');
    await waitPanel(/Dr\.? Tan/, 'memo_visible');
    await scrollToMemo();
    mark('memo_framed');
    await page.waitForTimeout(5000);
    mark('memo_hold_end');
    await frameSplit();
    mark('split_framed');
    const ask = candidate || APPT_ASK;
    const r = await seniorTurn(ask, 'senior', 'dad_appt');
    await page.waitForTimeout(4000);
    mark('hold_end');
    result.memo_text = APPT_MEMO; result.senior_text = ask;
    result.reply = r.reply; result.transcript = r.transcript; result.panel = await panelText();
    // Toasts such as "Could not parse server response" void the take.
    result.toasts = await page.evaluate(() => window.fyToasts || []);
    const low = r.reply.toLowerCase();
    result.check = {
      names_dr_tan: /dr\.?\s*tan\b/.test(low),
      names_thursday: /thursday/.test(low),
      names_10am: /\b10(:00)?\s*(a\.?m\.?|o'clock)|\bten\b/.test(low),
      no_toast: result.toasts.length === 0,
    };
    // Invented facts are judged by reading the reply; the check only covers what must be there.
    result.check.pass = Object.values(result.check).every(Boolean);
  } else if (shot === 'crisis') {
    const r1 = await seniorTurn(LONELY, 'lonely', 'dad_lonely');
    await page.waitForTimeout(2000);
    const panelAfterLonely = await panelText();
    mark('lonely_hold_end');
    const r2 = await seniorTurn(CRISIS, 'crisis', 'dad_crisis');
    if (!moments.crisis_flag_visible) await waitPanel(/Dad was told/, 'crisis_flag_visible');
    await page.waitForTimeout(6000);
    mark('hold_end');
    result.senior_text = [LONELY, CRISIS];
    result.reply = [r1.reply, r2.reply];
    result.panel_after_lonely = panelAfterLonely; result.panel = await panelText();
  } else {
    throw new Error(`unknown shot ${shot}`);
  }

  await page.waitForTimeout(500);
  await flash('sync_end');
  const video = page.video();
  await ctx.close();
  await browser.close();
  const wall = sec();

  const raw = await video.path();
  const webm = path.join(outDir, `${tag}.webm`);
  fs.copyFileSync(raw, webm);
  fs.rmSync(rawDir, { recursive: true, force: true });
  // Re-time on the two sync flashes: find the frames where the corner is magenta.
  const full = path.join(outDir, `_${tag}_full.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', webm, '-c:v', 'libx264', '-crf', '14',
    '-pix_fmt', 'yuv420p', '-r', '25', full]);
  const px = execFileSync('ffmpeg', ['-loglevel', 'error', '-i', full, '-vf', 'crop=16:16:1900:1060,scale=1:1',
    '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1 << 26 });
  const on = [];
  for (let i = 0; i + 2 < px.length; i += 3) on.push(px[i] > 190 && px[i + 1] < 90 && px[i + 2] > 190);
  const runs = [];
  on.forEach((v, i) => { if (v && !on[i - 1]) runs.push([i, i]); if (v) runs[runs.length - 1][1] = i; });
  if (runs.length < 2) throw new Error(`expected 2 sync flashes, found ${runs.length}`);
  const [a, b] = [runs[0], runs[runs.length - 1]];
  const vA = a[0] / 25, vB = b[0] / 25;                // video seconds of the two flashes
  const scale = (vB - vA) / (moments.sync_end - moments.sync_start);
  const toVideo = (s) => vA + (s - moments.sync_start) * scale;
  const clipStart = (a[1] + 1) / 25, clipEnd = b[0] / 25;  // flashes stay outside the clip
  const mp4 = path.join(outDir, `${tag}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', clipStart.toFixed(3), '-to', clipEnd.toFixed(3),
    '-i', full, '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', '25', mp4]);
  fs.rmSync(full);
  const dur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
    '-of', 'csv=p=0', mp4]).toString());
  const shift = (s) => +(toVideo(s) - clipStart).toFixed(2);
  result.sync = { video_flash_start: vA, video_flash_end: vB, clock_scale: +scale.toFixed(4) };
  result.clip = mp4; result.raw_clip = webm; result.duration = +dur.toFixed(2);
  const { sync_start, sync_end, ...km } = moments;
  result.key_moments = Object.fromEntries(Object.entries(km).map(([k, v]) => [k, shift(v)]));

  // One reply = one HLS playlist directory. Order its segments by the LAST playlist
  // served for it (the complete list) and join them into <tag>_reply[_n].wav.
  const lists = new Map();
  for (const a of audio) {
    const dir = a.url.split('?')[0].replace(/[^/]+$/, '');
    if (!lists.has(dir)) lists.set(dir, { segs: new Map(), playlist: '', first: a.at });
    const L = lists.get(dir);
    if (/\.m3u8/.test(a.url)) L.playlist = a.body.toString();
    else L.segs.set(a.url.split('?')[0].split('/').pop(), a);
  }
  result.reply_audio = [];
  let n = 0;
  for (const [dir, L] of lists) {
    const order = L.playlist.split('\n').filter(l => l && !l.startsWith('#'));
    // A reply's audio is used only when complete: the playlist ended and every segment it lists
    // was saved. A partial reply would cut the shot short while its caption runs in full.
    if (L.playlist && (!L.playlist.includes('#EXT-X-ENDLIST') || order.some(nm => !L.segs.has(nm)))) {
      throw new Error(`incomplete reply audio for ${dir}: ${order.filter(nm => !L.segs.has(nm)).length} segment(s) missing or the playlist never ended`);
    }
    const names = L.playlist ? order : [...L.segs.keys()];
    const files = [];
    names.forEach((nm, i) => {
      const a = L.segs.get(nm);
      const f = path.join(outDir, `_${tag}_seg${n}_${String(i).padStart(2, '0')}.${a.ext}`);
      fs.writeFileSync(f, a.body); files.push(f);
    });
    if (!files.length) continue;
    const out = path.join(outDir, `${tag}_reply${lists.size > 1 ? '_' + (n + 1) : ''}.wav`);
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', 'concat:' + files.join('|'), out]);
    files.forEach(f => fs.rmSync(f));
    const adur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
      '-of', 'csv=p=0', out]).toString());
    const firstPlay = plays.find(t => t >= L.first - 0.05);
    result.reply_audio.push({
      path: out, duration: +adur.toFixed(2), segments: files.length, playlist_url: dir + 'playlist.m3u8',
      first_served_at: shift(L.first), starts_playing_at: firstPlay !== undefined ? shift(firstPlay) : null,
    });
    n++;
  }
  // The player fires 'play' again on every buffered append; keep the first per reply only.
  result.audio_play_events = result.reply_audio.map(r => r.starts_playing_at);
  result.dad_turns = dadTurns.map(d => ({ ...d,
    mic_audio_start: result.key_moments[`${d.key}_mic_audio_start`] }));
  fs.writeFileSync(path.join(outDir, `${tag}.json`), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ ...result, panel: undefined, panel_after_lonely: undefined }, null, 2));
}

await main();
