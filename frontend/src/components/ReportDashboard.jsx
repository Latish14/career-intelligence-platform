// frontend/src/components/ReportDashboard.jsx

import ReportSummary from "./ReportSummary";
import SkillsSection from "./SkillsSection";
import RoadmapSection from "./RoadmapSection";

function ReportDashboard({ report }) {
  if (!report) {
    return (
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "2rem",
          textAlign: "center",
          color: "#6b7280",
        }}
      >
        No report available.
      </div>
    );
  }

  return (
    <div
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      <ReportSummary
        candidateName={
          report.candidate_name || "Unknown Candidate"
        }
        targetRole={
          report.target_role || "Not Specified"
        }
        placementScore={
          report.placement_score ?? 0
        }
        coveragePct={
          report.coverage_pct ?? 0
        }
      />

      <SkillsSection
        title="Detected Skills"
        skills={
          report.detected_skills || []
        }
      />

      <SkillsSection
        title="Missing Skills"
        skills={
          report.missing_skills || []
        }
      />

      <RoadmapSection
        roadmap={
          report.roadmap || []
        }
      />
    </div>
  );
}

export default ReportDashboard;
