/**
 * Safely coerce API values to arrays — prevents .map crashes on unexpected shapes.
 */
export function asArray(value) {
  return Array.isArray(value) ? value : [];
}

/**
 * Safely coerce a value to a display string.
 */
export function asText(value, fallback = "") {
  if (value == null) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

/**
 * Safely coerce a value to a number for display.
 */
export function asNumber(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

/**
 * Extract skill name from a skill item (object or plain string).
 */
export function skillName(item) {
  if (item == null) return "";
  if (typeof item === "string") return item;
  return asText(item.skill, "");
}
