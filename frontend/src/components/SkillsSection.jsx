import { useMemo, useState } from "react";
import { skillName } from "../utils/normalize";

function SkillsSection({ title, skills = [], variant = "detected" }) {
  const [query, setQuery] = useState("");
  const safeSkills = Array.isArray(skills) ? skills : [];
  const hasSkills = safeSkills.length > 0;
  const chipClass =
    variant === "missing" ? "skill-chip--missing" : "skill-chip--detected";
  const showSearch = hasSkills && safeSkills.length >= 4;

  const filteredSkills = useMemo(() => {
    if (!query.trim()) return safeSkills;

    const normalized = query.trim().toLowerCase();
    return safeSkills.filter((item) =>
      skillName(item).toLowerCase().includes(normalized)
    );
  }, [safeSkills, query]);

  return (
    <div className="card card--elevated card--hover">
      <div className="card__header">
        <div className="card__header-text">
          <h3 className="card__title">{title}</h3>
          {hasSkills && (
            <p className="card__subtitle">
              {variant === "detected"
                ? "Skills identified from your resume"
                : "Skills to develop for market alignment"}
            </p>
          )}
        </div>
        {hasSkills && (
          <span className="skills-count">{filteredSkills.length}</span>
        )}
      </div>

      {!hasSkills ? (
        <p className="card__empty">No skills available.</p>
      ) : (
        <>
          {showSearch && (
            <div className="skills-search">
              <svg
                className="skills-search__icon"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="search"
                className="skills-search__input"
                placeholder={`Search ${title.toLowerCase()}...`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label={`Filter ${title}`}
              />
            </div>
          )}

          {filteredSkills.length === 0 ? (
            <p className="card__empty">No skills match your search.</p>
          ) : (
            <div className="skills-list" role="list" aria-label={title}>
              {filteredSkills.map((item, index) => {
                const name = skillName(item) || "Unknown Skill";
                const confidence =
                  item &&
                  typeof item === "object" &&
                  item.confidence !== undefined &&
                  item.confidence !== null
                    ? Math.round(Number(item.confidence) * 100)
                    : null;

                return (
                  <span
                    key={`${name}-${index}`}
                    className={`skill-chip ${chipClass}`}
                    role="listitem"
                  >
                    <span>{name}</span>

                    {confidence !== null && !Number.isNaN(confidence) && (
                      <span className="skill-chip__confidence">
                        {confidence}%
                      </span>
                    )}
                  </span>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default SkillsSection;
