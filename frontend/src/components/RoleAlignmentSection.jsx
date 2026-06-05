import { asText, asNumber } from "../utils/normalize";

const RANK_LABELS = ["Best Match", "Second Match", "Third Match"];
const RANK_MEDALS = ["🥇", "🥈", "🥉"];

function getAlignmentStyle(pct, isBest) {
  if (isBest) {
    return {
      fillClass: "progress-bar__fill--accent",
      pctClass: "role-card__pct--accent",
    };
  }
  if (pct >= 70) {
    return {
      fillClass: "progress-bar__fill--success",
      pctClass: "role-card__pct--success",
    };
  }
  if (pct >= 40) {
    return {
      fillClass: "progress-bar__fill--warning",
      pctClass: "role-card__pct--warning",
    };
  }
  return {
    fillClass: "progress-bar__fill--neutral",
    pctClass: "role-card__pct--neutral",
  };
}

function RoleAlignmentSection({ roles = [] }) {
  const safeRoles = Array.isArray(roles) ? roles : [];

  return (
    <div className="card card--elevated card--hover">
      <div className="card__header">
        <div className="card__header-text">
          <h3 className="card__title">Career Role Alignment</h3>
          <p className="card__subtitle">
            Ranked by how well your profile fits each path
          </p>
        </div>
      </div>

      {safeRoles.length === 0 ? (
        <p className="card__empty">No alignment data available.</p>
      ) : (
        <div className="role-cards" role="list" aria-label="Role alignments">
          {safeRoles.map((role, index) => {
            if (!role || typeof role !== "object") return null;

            const pct = asNumber(role.alignment_pct, 0);
            const roleName = asText(role.role, "Unknown Role");
            const isBest = index === 0;
            const { fillClass, pctClass } = getAlignmentStyle(pct, isBest);
            const isTopThree = index < 3;
            const displayPct = Number.isInteger(pct) ? pct : pct.toFixed(1);

            return (
              <div
                key={`${roleName}-${index}`}
                className={`role-card${isBest ? " role-card--best" : ""}${isTopThree && !isBest ? " role-card--ranked" : ""}`}
                role="listitem"
              >
                {isBest && <div className="role-card__accent-bar" aria-hidden="true" />}

                <div className="role-card__header">
                  <div className="role-card__title-group">
                    {isTopThree && (
                      <span className="role-card__medal" aria-hidden="true">
                        {RANK_MEDALS[index]}
                      </span>
                    )}
                    <div>
                      <p className="role-card__name">{roleName}</p>
                      {isTopThree && (
                        <p className="role-card__rank-label">{RANK_LABELS[index]}</p>
                      )}
                    </div>
                  </div>

                  <span className={`role-card__pct ${pctClass}`}>{displayPct}%</span>
                </div>

                <div
                  className="progress-bar progress-bar--role"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${roleName} alignment`}
                >
                  <div
                    className={`progress-bar__fill ${fillClass}`}
                    style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
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

export default RoleAlignmentSection;
