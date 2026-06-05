import { asText, asNumber } from "../utils/normalize";

function formatCategory(category) {
  const text = asText(category);
  if (!text) return "General";
  return text.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getCategoryBadgeClass(category) {
  const normalized = asText(category).toLowerCase();
  if (normalized.includes("cloud") || normalized.includes("devops")) {
    return "badge--category-cloud";
  }
  if (normalized.includes("data") || normalized.includes("ml")) {
    return "badge--category-data";
  }
  if (normalized.includes("programming") || normalized.includes("language")) {
    return "badge--category-code";
  }
  return "badge--category";
}

function TrendingSkillsSection({ skills = [] }) {
  const safeSkills = Array.isArray(skills) ? skills : [];

  return (
    <div className="card card--elevated card--hover analytics-widget">
      <div className="card__header">
        <div className="card__header-text">
          <h3 className="card__title">Trending Market Skills</h3>
          <p className="card__subtitle">
            High-demand skills across current job listings
          </p>
        </div>
        {safeSkills.length > 0 && (
          <span className="widget-stat">{safeSkills.length} tracked</span>
        )}
      </div>

      {safeSkills.length === 0 ? (
        <p className="card__empty">No trend data available.</p>
      ) : (
        <div className="analytics-list" role="list" aria-label="Trending market skills">
          {safeSkills.map((skill, index) => {
            if (!skill || typeof skill !== "object") return null;

            const demandPct = asNumber(skill.demand_pct, 0);
            const name = asText(skill.skill, "Unknown");
            const isTopThree = index < 3;

            return (
              <div
                key={`${name}-${index}`}
                className={`progress-item${isTopThree ? " progress-item--featured" : ""}`}
                role="listitem"
              >
                <div className="progress-item__header">
                  <span
                    className={`progress-item__rank${isTopThree ? " progress-item__rank--top" : ""}`}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="progress-item__name">{name}</span>

                  <div className="progress-item__meta">
                    {skill.category && (
                      <span
                        className={`badge ${getCategoryBadgeClass(skill.category)}`}
                      >
                        {formatCategory(skill.category)}
                      </span>
                    )}
                    <span className="progress-item__value">{demandPct}%</span>
                  </div>
                </div>

                <div
                  className="progress-bar progress-bar--analytics"
                  role="progressbar"
                  aria-valuenow={demandPct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${name} demand`}
                >
                  <div
                    className="progress-bar__fill progress-bar__fill--accent"
                    style={{ width: `${Math.min(100, Math.max(0, demandPct))}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default TrendingSkillsSection;
