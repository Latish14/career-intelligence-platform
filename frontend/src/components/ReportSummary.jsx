import { asText, asNumber } from "../utils/normalize";
import { getPlacementTier } from "../utils/roadmapPhases";

function formatAlignment(value) {
  const num = asNumber(value, 0);
  return Number.isInteger(num) ? `${num}%` : `${num.toFixed(1)}%`;
}

function ReportSummary({
  candidateName,
  targetRole,
  placementScore,
  coveragePct,
  bestMatchRole,
  bestMatchPct,
}) {
  const placement = asNumber(placementScore, 0);
  const coverage = asNumber(coveragePct, 0);
  const placementTier = getPlacementTier(placement);
  const recommendedRole = asText(bestMatchRole, "Not available");
  const hasMatch = bestMatchRole != null && asText(bestMatchRole) !== "";

  return (
    <section className="report-hero" aria-label="Career intelligence summary">
      <div className="report-hero__header">
        <p className="report-hero__eyebrow">Career Intelligence Report</p>
        <p className="report-hero__candidate">{asText(candidateName, "Unknown Candidate")}</p>
      </div>

      <div className="report-hero__focal">
        <p className="report-hero__focal-label">
          <span aria-hidden="true">🎯</span> Recommended Career Path
        </p>
        <h2 className="report-hero__focal-role">{recommendedRole}</h2>
        {hasMatch && bestMatchPct != null && Number.isFinite(Number(bestMatchPct)) && (
          <p className="report-hero__focal-alignment">
            {formatAlignment(bestMatchPct)} Alignment
          </p>
        )}
        <p className="report-hero__target">
          Target Role: <span>{asText(targetRole, "Not Specified")}</span>
        </p>
      </div>

      <div className="kpi-row">
        <div className={`kpi-card kpi-card--placement kpi-card--${placementTier}`}>
          <p className="kpi-card__label">Placement Score</p>
          <p className="kpi-card__value kpi-card__value--xl">{placement}</p>
          <p className="kpi-card__unit">out of 100</p>
        </div>

        <div className="kpi-card kpi-card--coverage">
          <p className="kpi-card__label">Coverage Score</p>
          <p className="kpi-card__value kpi-card__value--lg">{coverage}%</p>
          <div
            className="kpi-card__progress"
            role="progressbar"
            aria-valuenow={coverage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Skill coverage"
          >
            <div
              className="kpi-card__progress-fill"
              style={{ width: `${Math.min(100, Math.max(0, coverage))}%` }}
            />
          </div>
          <p className="kpi-card__unit">skill match rate</p>
        </div>

        <div className="kpi-card kpi-card--match">
          <p className="kpi-card__label">Best Career Match</p>
          <p className="kpi-card__value kpi-card__value--role">{recommendedRole}</p>
          {hasMatch && bestMatchPct != null && Number.isFinite(Number(bestMatchPct)) && (
            <p className="kpi-card__match-pct">{formatAlignment(bestMatchPct)} alignment</p>
          )}
        </div>
      </div>
    </section>
  );
}

export default ReportSummary;
