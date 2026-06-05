import { asText } from "./normalize";

const MAJOR_PHASE_LABELS = [
  "Foundations",
  "Core Development",
  "Cloud & DevOps",
  "Specialization",
  "Advanced Engineering",
  "Leadership & Scale",
];

const CATEGORY_PHASE_MAP = {
  programming_language: "Foundations",
  database: "Foundations",
  data_engineering: "Foundations",
  soft_skill: "Foundations",
  devops: "Cloud & DevOps",
  cloud: "Cloud & DevOps",
  machine_learning: "Specialization",
  data_science: "Specialization",
  backend: "Core Development",
  frontend: "Core Development",
  security: "Advanced Engineering",
  other: "Core Development",
};

const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };

/**
 * Group roadmap skills into 4–6 meaningful learning phases.
 * Uses category when available, otherwise distributes by priority + order.
 */
export function groupRoadmapIntoMajorPhases(roadmap, maxPhases = 5) {
  if (!Array.isArray(roadmap) || roadmap.length === 0) return [];

  const sorted = [...roadmap]
    .filter((item) => item && typeof item === "object")
    .sort((a, b) => {
      const weekDiff = (Number(a.week) || 0) - (Number(b.week) || 0);
      if (weekDiff !== 0) return weekDiff;

      const priA = PRIORITY_ORDER[asText(a.priority).toLowerCase()] ?? 1;
      const priB = PRIORITY_ORDER[asText(b.priority).toLowerCase()] ?? 1;
      return priA - priB;
    });

  const hasCategories = sorted.some((item) => item.category);

  if (hasCategories) {
    const phaseMap = new Map();

    sorted.forEach((item) => {
      const category = asText(item.category, "other").toLowerCase();
      const phaseTitle =
        CATEGORY_PHASE_MAP[category] ||
        category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

      if (!phaseMap.has(phaseTitle)) {
        phaseMap.set(phaseTitle, []);
      }
      phaseMap.get(phaseTitle).push(item);
    });

    let phases = Array.from(phaseMap.entries()).map(([title, items]) => ({
      title,
      items,
      skillNames: items.map((i) => asText(i.skill, "Unknown")).join(", "),
    }));

    if (phases.length > maxPhases) {
      phases = mergeSmallestPhases(phases, maxPhases);
    }

    return phases;
  }

  const phaseCount = Math.min(
    maxPhases,
    Math.max(1, Math.ceil(sorted.length / 3))
  );
  const chunkSize = Math.ceil(sorted.length / phaseCount);

  const phases = [];
  for (let i = 0; i < phaseCount; i += 1) {
    const items = sorted.slice(i * chunkSize, (i + 1) * chunkSize);
    if (items.length === 0) continue;

    phases.push({
      title: MAJOR_PHASE_LABELS[i] || `Phase ${i + 1}`,
      items,
      skillNames: items.map((item) => asText(item.skill, "Unknown")).join(", "),
    });
  }

  return phases;
}

function mergeSmallestPhases(phases, targetCount) {
  const merged = [...phases];

  while (merged.length > targetCount) {
    merged.sort((a, b) => a.items.length - b.items.length);
    const smallest = merged.shift();
    const next = merged.shift();
    merged.push({
      title: next.title,
      items: [...smallest.items, ...next.items],
      skillNames: [...smallest.items, ...next.items]
        .map((i) => asText(i.skill, "Unknown"))
        .join(", "),
    });
    merged.sort((a, b) => {
      const weekA = Number(a.items[0]?.week) || 0;
      const weekB = Number(b.items[0]?.week) || 0;
      return weekA - weekB;
    });
  }

  return merged;
}

export function getPlacementTier(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return "weak";
  if (value >= 70) return "strong";
  if (value >= 40) return "medium";
  return "weak";
}
