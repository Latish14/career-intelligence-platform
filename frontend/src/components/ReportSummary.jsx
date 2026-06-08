import { asText, asNumber } from "../utils/normalize";
import { getPlacementTier } from "../utils/roadmapPhases";
import DownloadButton from "./DownloadButton";

function formatAlignment(value) {
  const num = asNumber(value, 0);
  return Number.isInteger(num) ? `${num}%` : `${num.toFixed(1)}%`;
}

function CircularProgress({ value, colorClass }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className="circular-progress">
      <svg className="circular-progress__svg" viewBox="0 0 64 64">
        <circle className="circular-progress__track" cx="32" cy="32" r={radius} />
        <circle 
          className={`circular-progress__fill ${colorClass}`} 
          cx="32" cy="32" r={radius} 
          style={{ strokeDasharray: circumference, strokeDashoffset }}
        />
      </svg>
    </div>
  );
}

function ReportSummary({
  candidateName,
  targetRole,
  placementScore,
  coveragePct,
  bestMatchRole,
  bestMatchPct,
  onDownload,
  downloadStatus = "idle",
  downloadProgress = 0,
}) {
  const placement = asNumber(placementScore, 0);
  const coverage = asNumber(coveragePct, 0);
  const placementTier = getPlacementTier(placement);
  const recommendedRole = asText(bestMatchRole, "Not available");
  const hasMatch = bestMatchRole != null && asText(bestMatchRole) !== "";
  const matchPctValue = asNumber(bestMatchPct, 0);

  return (
    <section className="hero-grid" aria-label="Career intelligence summary">
      <div className="hero-grid__left">
        <div className="hero-grid__left-top-action">
          <DownloadButton 
            onClick={onDownload} 
            downloadStatus={downloadStatus} 
            progress={downloadProgress} 
          />
        </div>
        <div className="hero-grid__left-content">
          <p className="hero-grid__candidate">{asText(candidateName, "Unknown Candidate")}</p>
          
          <div className="hero-grid__focal">
            <p className="hero-grid__eyebrow">BEST CAREER MATCH</p>
            <h2 className="hero-grid__role">{recommendedRole}</h2>
            
            {hasMatch && (
              <div className="hero-grid__alignment">
                <span className="hero-grid__alignment-val">{formatAlignment(matchPctValue)}</span>
                <span className="hero-grid__alignment-lbl">Alignment</span>
              </div>
            )}
            
            {hasMatch && (
              <div className="hero-grid__progress" role="progressbar" aria-valuenow={matchPctValue} aria-valuemin={0} aria-valuemax={100}>
                <div className="hero-grid__progress-fill" style={{ width: `${Math.min(100, Math.max(0, matchPctValue))}%` }} />
              </div>
            )}
            
            <div className="hero-grid__target">
              <span className="hero-grid__target-lbl">Target Role</span>
              <span className="hero-grid__target-val">{asText(targetRole, "Not Specified")}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="hero-grid__right">
        {/* Card 1: Placement Score */}
        <div className="hero-metric-card">
          <div className="hero-metric-card__content">
            <p className="hero-metric-card__label">Placement Score</p>
            <p className={`hero-metric-card__value hero-metric-card__value--${placementTier}`}>{placement}</p>
          </div>
          <CircularProgress value={placement} colorClass={`circular-progress__fill--${placementTier}`} />
        </div>

        {/* Card 2: Coverage Score */}
        <div className="hero-metric-card">
          <div className="hero-metric-card__content">
            <p className="hero-metric-card__label">Coverage Score</p>
            <p className="hero-metric-card__value hero-metric-card__value--coverage">{coverage}%</p>
            <div className="hero-metric-card__bar">
              <div className="hero-metric-card__bar-fill hero-metric-card__bar-fill--coverage" style={{ width: `${Math.min(100, Math.max(0, coverage))}%` }} />
            </div>
          </div>
        </div>

        {/* Card 3: Top Career Recommendation */}
        <div className="hero-metric-card">
          <div className="hero-metric-card__content">
            <p className="hero-metric-card__label">Top Career Recommendation</p>
            <p className="hero-metric-card__value hero-metric-card__value--role" title={recommendedRole}>{recommendedRole}</p>
            {hasMatch && (
              <p className="hero-metric-card__sub">{formatAlignment(matchPctValue)} Alignment</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default ReportSummary;
