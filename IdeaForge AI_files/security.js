const DIFFICULTY_CLASSES = new Set(["easy", "medium", "hard"]);
const STATUS_CLASSES = new Set(["planning", "active", "completed", "paused", "cancelled"]);

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

export function diffClass(difficulty) {
  const value = String(difficulty ?? "medium").toLowerCase();
  return DIFFICULTY_CLASSES.has(value) ? `difficulty-${value}` : "difficulty-medium";
}

export function statusClass(status) {
  const value = String(status ?? "").toLowerCase();
  return STATUS_CLASSES.has(value) ? `status-${value}` : "";
}

export function safeScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(100, Math.max(0, number));
}

export function safeId(value) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}

export function idAttr(value) {
  return String(safeId(value) ?? "");
}

export function scoreColor(value) {
  const score = safeScore(value);
  return score >= 70 ? "var(--accent)" : score >= 45 ? "var(--primary)" : "var(--danger)";
}
