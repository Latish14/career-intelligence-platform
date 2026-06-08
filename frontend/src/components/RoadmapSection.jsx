import { useMemo, useState } from "react";
import { asText } from "../utils/normalize";
import { groupRoadmapIntoMajorPhases } from "../utils/roadmapPhases";

function getPriorityBadgeClass(priority) {
  const normalized = asText(priority).toLowerCase();

  if (normalized.includes("high")) return "badge--priority-high";
  if (normalized.includes("medium")) return "badge--priority-medium";
  return "badge--priority-low";
}

function RoadmapSection({ roadmap = [] }) {
  const [expandedPhase, setExpandedPhase] = useState(0);
  const safeRoadmap = Array.isArray(roadmap) ? roadmap : [];
  const hasRoadmap = safeRoadmap.length > 0;

  const phases = useMemo(
    () => (hasRoadmap ? groupRoadmapIntoMajorPhases(safeRoadmap, 5) : []),
    [safeRoadmap, hasRoadmap]
  );

  const togglePhase = (index) => {
    setExpandedPhase((current) => (current === index ? -1 : index));
  };

  return (
    <div className="card card--elevated">
      <div className="card__header">
        <div className="card__header-text">
          <h3 className="card__title">Learning Roadmap</h3>
          <p className="card__subtitle">
            {hasRoadmap
              ? `${phases.length} learning phase${phases.length !== 1 ? "s" : ""} · ${safeRoadmap.length} skill${safeRoadmap.length !== 1 ? "s" : ""}`
              : "Personalized skill development plan"}
          </p>
        </div>
      </div>

      {!hasRoadmap ? (
        <p className="card__empty">No roadmap available.</p>
      ) : (
        <div className="accordion" role="list" aria-label="Learning roadmap phases">
          {phases.map((phase, index) => {
            const isOpen = expandedPhase === index;

            return (
              <div
                key={`${phase.title}-${index}`}
                className={`accordion__item${isOpen ? " accordion__item--open" : ""}`}
                role="listitem"
              >
                <button
                  type="button"
                  className="accordion__trigger"
                  onClick={() => togglePhase(index)}
                  aria-expanded={isOpen}
                  aria-controls={`roadmap-phase-${index}`}
                >
                  <div className="accordion__trigger-left">
                    <svg
                      className="accordion__chevron"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      aria-hidden="true"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                    <div>
                      <p className="accordion__phase-title">{phase.title}</p>
                      {!isOpen && (
                        <p className="accordion__phase-skills">{phase.skillNames}</p>
                      )}
                    </div>
                  </div>
                  <span className="skills-count">{phase.items.length}</span>
                </button>

                <div
                  id={`roadmap-phase-${index}`}
                  className="accordion__panel"
                  role="region"
                  aria-hidden={!isOpen}
                >
                  <div className="accordion__panel-inner">
                    <div className="accordion__content">
                      {phase.items.map((item, itemIndex) => (
                        <div
                          key={`${asText(item.skill)}-${itemIndex}`}
                          className="accordion__skill-row"
                        >
                          <div className="accordion__skill-main">
                            <p className="accordion__skill-name">
                              {asText(item.skill, "Unknown Skill")}
                            </p>
                            <p className="accordion__skill-reason">
                              {asText(item.reason, "No details available.")}
                            </p>
                          </div>

                          <div className="accordion__skill-meta">
                            <span
                              className={`badge ${getPriorityBadgeClass(item.priority)}`}
                              title={asText(item.priority, "Medium")}
                            />
                            <span className="accordion__skill-duration">
                              {Number(item.duration_weeks) || 1} wk
                              {(Number(item.duration_weeks) || 1) > 1 ? "s" : ""}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default RoadmapSection;
