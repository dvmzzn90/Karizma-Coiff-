// Rendu image par image de bip.html -> MP4 1080x1920 30 fps avec audio.
// Usage : node render.js            (vidéo complète)
//         node render.js --stills 2,5.5,12   (captures PNG de contrôle)
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

(async () => {
  const here = __dirname;
  const out = path.join(here, "build");
  const args = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on("pageerror", e => { console.error("PAGE ERROR", e); process.exit(1); });
  await page.goto("file://" + path.join(here, "bip.html") + "?render=1");
  await page.evaluate(() => document.fonts.load('800 50px "Baloo 2"'));
  const dur = await page.evaluate(() => window.DURATION);
  const svg = await page.$("#stage");

  if (args[0] === "--stills") {
    const times = args[1].split(",").map(Number);
    fs.mkdirSync(path.join(out, "stills"), { recursive: true });
    for (const t of times) {
      await page.evaluate(t => window.render(t), t);
      await svg.screenshot({ path: path.join(out, "stills", `t${t.toFixed(2)}.png`) });
    }
    await browser.close();
    return;
  }

  const fps = 30, n = Math.ceil(dur * fps);
  const silent = path.join(out, "video_silent.mp4");
  const ff = spawn("ffmpeg", ["-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", silent], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.render(t), i / fps);
    const buf = await svg.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    if (i % 150 === 0) console.log(`frame ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on("close", r));
  await browser.close();
  const final = path.join(here, "bip_argent_placard.mp4");
  await new Promise((res, rej) => spawn("ffmpeg", ["-loglevel", "error", "-y", "-i", silent, "-i", path.join(out, "audio.wav"),
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final], { stdio: "inherit" })
    .on("close", c => c ? rej(c) : res()));
  console.log("OK ->", final);
})();
