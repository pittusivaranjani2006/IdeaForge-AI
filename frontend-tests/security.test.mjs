import test from "node:test";
import assert from "node:assert/strict";
import {
  escapeHtml,
  diffClass,
  statusClass,
  safeScore,
  safeId,
  idAttr,
  scoreColor,
} from "../IdeaForge AI_files/security.js";

test("escapeHtml encodes dangerous characters", () => {
  assert.equal(
    escapeHtml(`<script>alert("x")</script> & 'y'`),
    "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#039;y&#039;"
  );
});

test("diffClass allowlists difficulty values", () => {
  assert.equal(diffClass("Easy"), "difficulty-easy");
  assert.equal(diffClass("hard"), "difficulty-hard");
  assert.equal(diffClass("easy\" onmouseover=\"x"), "difficulty-medium");
  assert.equal(diffClass(null), "difficulty-medium");
});

test("statusClass allowlists project statuses", () => {
  assert.equal(statusClass("active"), "status-active");
  assert.equal(statusClass("COMPLETED"), "status-completed");
  assert.equal(statusClass("cancelled\" onclick=\"x"), "");
  assert.equal(statusClass(undefined), "");
});

test("safeScore clamps and rejects invalid numbers", () => {
  assert.equal(safeScore(72), 72);
  assert.equal(safeScore(-10), 0);
  assert.equal(safeScore(140), 100);
  assert.equal(safeScore("85"), 85);
  assert.equal(safeScore("90%; color:red"), 0);
});

test("safeId accepts only positive integers", () => {
  assert.equal(safeId("12"), 12);
  assert.equal(safeId(7), 7);
  assert.equal(safeId("1\" onclick=\"x"), null);
  assert.equal(safeId(0), null);
  assert.equal(safeId(-3), null);
  assert.equal(safeId("1.5"), null);
});

test("idAttr emits empty string for invalid ids", () => {
  assert.equal(idAttr("12"), "12");
  assert.equal(idAttr("1\" onclick=\"x"), "");
});

test("scoreColor uses the safe score", () => {
  assert.equal(scoreColor("95"), "var(--accent)");
  assert.equal(scoreColor("50"), "var(--primary)");
  assert.equal(scoreColor("10"), "var(--danger)");
  assert.equal(scoreColor("bad"), "var(--danger)");
});
