import { useState } from "react";
import ReportSummary from "./ReportSummary";
import SkillsSection from "./SkillsSection";
import RoadmapSection from "./RoadmapSection";
import TrendingSkillsSection from "./TrendingSkillsSection";
import RoleAlignmentSection from "./RoleAlignmentSection";
import { asArray } from "../utils/normalize";
import { exportCareerReportPDF } from "../utils/pdfExport";

function SectionDivider({ label }) {
  return (
    <div className="section-divider">
      <span className="section-divider__label">{label}</span>
      <div className="section-divider__line" />
    </div>
  );
}

function ReportDashboard({ report }) {
  const [downloadStatus, setDownloadStatus] = useState("idle");
  const [downloadProgress, setDownloadProgress] = useState(0);

  if (!report || typeof report !== "object") {
    return <p className="card__empty">No report available.</p>;
  }

  const roleAlignments = asArray(report.role_alignments);
  const bestMatch = roleAlignments[0];

  const handleDownload = async () => {
    if (downloadStatus !== "idle") return;
    
    setDownloadStatus("generating");
    setDownloadProgress(0);
    
    // Fake progress animation
    const interval = setInterval(() => {
      setDownloadProgress(p => (p >= 90 ? 90 : p + 15));
    }, 200);

    // Give UI a moment to show generating state, then run sync PDF export
    setTimeout(() => {
      try {
        exportCareerReportPDF(report);
        clearInterval(interval);
        setDownloadProgress(100);
        setDownloadStatus("success");
        
        setTimeout(() => {
          setDownloadStatus("idle");
          setDownloadProgress(0);
        }, 3000);
      } catch (err) {
        console.error("PDF export failed:", err);
        clearInterval(interval);
        setDownloadStatus("idle");
      }
    }, 600);
  };

  return (
    <div className="dashboard dashboard--visible">
      <ReportSummary
        candidateName={report.candidate_name || "Unknown Candidate"}
        targetRole={report.target_role || "Not Specified"}
        placementScore={report.placement_score ?? 0}
        coveragePct={report.coverage_pct ?? 0}
        bestMatchRole={bestMatch?.role}
        bestMatchPct={bestMatch?.alignment_pct}
        onDownload={handleDownload}
        downloadStatus={downloadStatus}
        downloadProgress={downloadProgress}
      />

      <SectionDivider label="Career Alignment" />
      <RoleAlignmentSection roles={roleAlignments} />

      <SectionDivider label="Market Intelligence" />
      <TrendingSkillsSection skills={asArray(report.trending_skills)} />

      <SectionDivider label="Skills Analysis" />
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

      <SectionDivider label="Learning Roadmap" />
      <RoadmapSection roadmap={asArray(report.roadmap)} />
    </div>
  );
}

export default ReportDashboard;
