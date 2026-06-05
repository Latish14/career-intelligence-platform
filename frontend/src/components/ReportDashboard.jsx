import ReportSummary from "./ReportSummary";
import SkillsSection from "./SkillsSection";
import RoadmapSection from "./RoadmapSection";
import TrendingSkillsSection from "./TrendingSkillsSection";
import RoleAlignmentSection from "./RoleAlignmentSection";
import { asArray } from "../utils/normalize";

function ReportDashboard({ report }) {
  if (!report || typeof report !== "object") {
    return <p className="card__empty">No report available.</p>;
  }

  const roleAlignments = asArray(report.role_alignments);
  const bestMatch = roleAlignments[0];

  return (
    <div className="dashboard dashboard--visible">
      <ReportSummary
        candidateName={report.candidate_name || "Unknown Candidate"}
        targetRole={report.target_role || "Not Specified"}
        placementScore={report.placement_score ?? 0}
        coveragePct={report.coverage_pct ?? 0}
        bestMatchRole={bestMatch?.role}
        bestMatchPct={bestMatch?.alignment_pct}
      />

      <div className="dashboard__section">
        <h2 className="dashboard__section-title">Skills Analysis</h2>
        <div className="dashboard__grid-skills">
          <SkillsSection
            title="Detected Skills"
            skills={asArray(report.detected_skills)}
            variant="detected"
          />

          <SkillsSection
            title="Missing Skills"
            skills={asArray(report.missing_skills)}
            variant="missing"
          />
        </div>
      </div>

      <RoadmapSection roadmap={asArray(report.roadmap)} />

      <div className="dashboard__grid-2">
        <TrendingSkillsSection skills={asArray(report.trending_skills)} />
        <RoleAlignmentSection roles={roleAlignments} />
      </div>
    </div>
  );
}

export default ReportDashboard;
