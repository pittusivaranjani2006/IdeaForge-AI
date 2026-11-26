import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = relativePath => readFile(new URL(relativePath, root), "utf8");

async function cspDirective() {
  const headers = await read("_headers");
  const line = headers.split(/\r?\n/).find(value => value.includes("Content-Security-Policy:"));
  assert.ok(line, "Content-Security-Policy header is present");
  return line.replace(/^\s*Content-Security-Policy:\s*/, "");
}

test("CSP keeps script execution strict and avoids inline-style exceptions", async () => {
  const csp = await cspDirective();
  assert.match(csp, /script-src 'self'/);
  assert.match(csp, /style-src 'self' https:\/\/fonts\.googleapis\.com/);
  assert.match(csp, /font-src 'self' https:\/\/fonts\.gstatic\.com/);
  assert.match(csp, /connect-src 'self'/);
  assert.doesNotMatch(csp, /unsafe-inline/i);
  assert.doesNotMatch(csp, /unsafe-eval/i);
  assert.doesNotMatch(csp, /style-src-attr/i);
});

test("application uses no inline styles or CSSOM style assignments", async () => {
  const app = await read("IdeaForge AI_files/app.js");
  assert.doesNotMatch(app, /style="/);
  assert.doesNotMatch(app, /\.style\./);
});

test("auth error and explorer empty state use hidden semantics", async () => {
  const app = await read("IdeaForge AI_files/app.js");
  const css = await read("IdeaForge AI_files/styles.css");
  assert.match(app, /class="auth-error hidden"/);
  assert.match(app, /errEl\.hidden = true/);
  assert.match(app, /el\.hidden = false/);
  assert.match(app, /empty\.hidden = items\.length > 0/);
  assert.match(css, /\[hidden\],\s*\.hidden\s*\{\s*display: none !important/);
});

test("evaluation score states use CSP-safe score classes", async () => {
  const app = await read("IdeaForge AI_files/app.js");
  const css = await read("IdeaForge AI_files/styles.css");
  assert.match(app, /function scoreClass\(value\)/);
  assert.match(app, /eval-score-ring \$\{scoreClass\(ev\.overall_score\)\}/);
  assert.match(app, /score-bar \$\{scoreClass\(s\.val\)\}/);
  assert.match(app, /text-score \$\{scoreClass\(s\.val\)\}/);
  assert.match(css, /\.eval-score-ring[^}]*conic-gradient/);
  assert.match(css, /\.score-bar[^}]*width: var\(--score-pct/);
  assert.match(css, /\.text-score[^}]*var\(--score-color/);
  assert.match(css, /\.score-0\s*\{[^}]*--score-pct: 0%/);
  assert.match(css, /\.score-44\s*\{[^}]*var\(--danger\)/);
  assert.match(css, /\.score-45\s*\{[^}]*var\(--primary\)/);
  assert.match(css, /\.score-69\s*\{[^}]*var\(--primary\)/);
  assert.match(css, /\.score-70\s*\{[^}]*var\(--accent\)/);
  assert.match(css, /\.score-100\s*\{[^}]*--score-pct: 100%/);
});

test("project and roadmap progress states use CSP-safe classes", async () => {
  const app = await read("IdeaForge AI_files/app.js");
  const css = await read("IdeaForge AI_files/styles.css");
  assert.match(app, /progress-bar \$\{scoreClass\(p\.progress_pct\)\}/);
  assert.match(app, /progress-bar \$\{scoreClass\(proj\.progress_pct\)\}/);
  assert.match(app, /bar\.className = `progress-bar \$\{scoreClass\(updated\.progress_pct\)\}`/);
  assert.match(css, /\.progress-bar[^}]*width: var\(--score-pct/);
  assert.match(css, /\.progress-wrap-spaced/);
});

test("health banner remains visible only when backend is unavailable", async () => {
  const app = await read("IdeaForge AI_files/app.js");
  const css = await read("IdeaForge AI_files/styles.css");
  assert.match(app, /banner\.hidden = true/);
  assert.match(app, /banner\.hidden = available/);
  assert.match(css, /\.health-banner\[hidden\]/);
  assert.match(css, /\.health-banner\s*\{/);
});

test("Google Fonts, CSS, and ES modules are allowed by the final CSP", async () => {
  const html = await read("IdeaForge AI.html");
  const fontCss = await read("IdeaForge AI_files/css2");
  const csp = await cspDirective();
  assert.match(html, /rel="stylesheet" href="\.\/IdeaForge AI_files\/styles\.css"/);
  assert.match(html, /href="\.\/IdeaForge AI_files\/css2"/);
  assert.match(html, /type="module" src="\.\/IdeaForge AI_files\/app\.js"/);
  assert.match(fontCss, /https:\/\/fonts\.gstatic\.com/);
  assert.match(csp, /font-src 'self' https:\/\/fonts\.gstatic\.com/);
  assert.match(csp, /style-src 'self' https:\/\/fonts\.googleapis\.com/);
});
