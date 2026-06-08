import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

// ─── Design tokens ───────────────────────────────────────────────────────────
const BLUE   = [37, 99, 235];   // #2563eb
const DARK   = [17, 24, 39];    // #111827
const GRAY   = [107, 114, 128]; // #6b7280
const LGRAY  = [229, 231, 235]; // #e5e7eb
const WHITE  = [255, 255, 255];
const LBLUE  = [239, 246, 255]; // #eff6ff

const FONT_TITLE  = 22;
const FONT_H1     = 13;
const FONT_H2     = 11;
const FONT_BODY   = 10;
const FONT_SMALL  = 8;

const MARGIN = 18; // left/right page margin in mm

// ─── Helpers ─────────────────────────────────────────────────────────────────

function pageWidth(doc) {
  return doc.internal.pageSize.getWidth();
}

function pageHeight(doc) {
  return doc.internal.pageSize.getHeight();
}

/** Draw a filled rectangle */
function fillRect(doc, x, y, w, h, color) {
  doc.setFillColor(...color);
  doc.rect(x, y, w, h, "F");
}

/** Centered text */
function centeredText(doc, text, y, size, color = DARK, style = "normal") {
  doc.setFontSize(size);
  doc.setTextColor(...color);
  doc.setFont("helvetica", style);
  doc.text(String(text), pageWidth(doc) / 2, y, { align: "center" });
}

/** Left-aligned section heading with colored accent bar */
function sectionHeading(doc, label, y) {
  fillRect(doc, MARGIN, y, 3, 5, BLUE);
  doc.setFontSize(FONT_H1);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...BLUE);
  doc.text(label, MARGIN + 6, y + 4.2);
  return y + 11;
}

/** Thin horizontal rule */
function hrule(doc, y, color = LGRAY) {
  doc.setDrawColor(...color);
  doc.setLineWidth(0.3);
  doc.line(MARGIN, y, pageWidth(doc) - MARGIN, y);
}

/** Add page footer with page numbers */
function addFooters(doc) {
  const total = doc.internal.getNumberOfPages();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    const pw = pageWidth(doc);
    const ph = pageHeight(doc);

    fillRect(doc, 0, ph - 10, pw, 10, [249, 250, 251]);
    hrule(doc, ph - 10, LGRAY);

    doc.setFontSize(FONT_SMALL);
    doc.setTextColor(...GRAY);
    doc.setFont("helvetica", "normal");
    doc.text("Career Intelligence Platform", MARGIN, ph - 3.5);
    doc.text(`Page ${i} of ${total}`, pw - MARGIN, ph - 3.5, { align: "right" });
  }
}

/** Safe array coerce (mirrors your normalize util) */
function toArr(val) {
  if (Array.isArray(val)) return val;
  if (val && typeof val === "object") return Object.values(val);
  return [];
}

/** Check remaining space and add a new page if needed */
function ensureSpace(doc, y, needed = 30) {
  if (y + needed > pageHeight(doc) - 18) {
    doc.addPage();
    return 22;
  }
  return y;
}

// ─── autoTable shared theme ───────────────────────────────────────────────────
function tableTheme(doc, startY, head, body, columnStyles = {}) {
  autoTable(doc, {
    startY,
    head,
    body,
    theme: "grid",
    styles: {
      fontSize: FONT_BODY,
      cellPadding: { top: 3, bottom: 3, left: 4, right: 4 },
      textColor: DARK,
      lineColor: LGRAY,
      lineWidth: 0.25,
    },
    headStyles: {
      fillColor: BLUE,
      textColor: WHITE,
      fontStyle: "bold",
      fontSize: FONT_BODY,
    },
    alternateRowStyles: { fillColor: LBLUE },
    columnStyles,
    margin: { left: MARGIN, right: MARGIN },
  });
  return doc.lastAutoTable.finalY + 8;
}

// ─── Sections ────────────────────────────────────────────────────────────────

/** Cover page */
function drawCover(doc, report) {
  const pw = pageWidth(doc);
  const ph = pageHeight(doc);

  // Deep blue header band
  fillRect(doc, 0, 0, pw, 68, BLUE);

  // Logo / brand mark
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...WHITE);
  fillRect(doc, MARGIN, 12, 24, 10, [29, 78, 216]);
  doc.text("CIP", MARGIN + 12, 18.5, { align: "center" });

  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.text("Career Intelligence Platform", MARGIN + 27, 18.5);

  // Main headline
  centeredText(doc, "Career Intelligence Report", 42, FONT_TITLE, WHITE, "bold");
  centeredText(doc, "AI-Powered Career Analysis", 51, FONT_H2, [186, 214, 255], "normal");

  // Decorative band
  fillRect(doc, 0, 68, pw, 2, [29, 78, 216]);

  // Candidate card
  fillRect(doc, MARGIN, 82, pw - MARGIN * 2, 58, [249, 250, 251]);
  doc.setDrawColor(...LGRAY);
  doc.setLineWidth(0.4);
  doc.rect(MARGIN, 82, pw - MARGIN * 2, 58);

  centeredText(doc, report.candidate_name || "Unknown Candidate", 98, 16, DARK, "bold");
  centeredText(doc, "Target Role", 109, FONT_SMALL, GRAY, "normal");
  centeredText(doc, report.target_role || "Not Specified", 117, FONT_H1, BLUE, "bold");

  hrule(doc, 126, LGRAY);

  centeredText(doc, `Report Generated: ${new Date().toLocaleDateString("en-IN", {
    year: "numeric", month: "long", day: "numeric",
  })}`, 134, FONT_SMALL, GRAY, "normal");

  // Metric pills at bottom of cover
  const metrics = [
    { label: "Placement Score", value: `${report.placement_score ?? 0}%` },
    { label: "Coverage Score",  value: `${report.coverage_pct ?? 0}%` },
  ];
  const roleAlignments = toArr(report.role_alignments);
  if (roleAlignments[0]) {
    metrics.push({ label: "Best Match", value: roleAlignments[0].role || "—" });
  }

  const pillW = (pw - MARGIN * 2 - (metrics.length - 1) * 6) / metrics.length;
  metrics.forEach((m, i) => {
    const x = MARGIN + i * (pillW + 6);
    fillRect(doc, x, 153, pillW, 22, LBLUE);
    doc.setDrawColor(...BLUE);
    doc.setLineWidth(0.3);
    doc.rect(x, 153, pillW, 22);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...BLUE);
    doc.text(String(m.value), x + pillW / 2, 162, { align: "center" });
    doc.setFontSize(FONT_SMALL);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...GRAY);
    doc.text(m.label, x + pillW / 2, 170, { align: "center" });
  });

  // Footer note
  centeredText(doc, "Confidential · For Recruiter Use Only", ph - 14, FONT_SMALL, GRAY, "normal");
}

/** Summary metrics page */
function drawSummary(doc, report) {
  doc.addPage();
  let y = 22;

  y = sectionHeading(doc, "Executive Summary", y);
  hrule(doc, y);
  y += 8;

  const roleAlignments = toArr(report.role_alignments);
  const best = roleAlignments[0];

  const rows = [
    ["Candidate Name",        report.candidate_name || "—"],
    ["Target Role",           report.target_role || "—"],
    ["Placement Score",       `${report.placement_score ?? 0}%`],
    ["Coverage Score",        `${report.coverage_pct ?? 0}%`],
    ["Best Career Match",     best?.role || "—"],
    ["Alignment Percentage",  best ? `${best.alignment_pct ?? 0}%` : "—"],
  ];

  y = tableTheme(doc, y,
    [["Metric", "Value"]],
    rows,
    {
      0: { fontStyle: "bold", cellWidth: 70 },
      1: { cellWidth: "auto" },
    }
  );

  return y;
}

/** Skills section (detected + missing on same page) */
function drawSkills(doc, report, startY) {
  let y = ensureSpace(doc, startY, 40);
  if (y < 25) y = 22; // fresh page

  y = sectionHeading(doc, "Skills Analysis", y);
  hrule(doc, y);
  y += 8;

  const detected = toArr(report.detected_skills);
  const missing  = toArr(report.missing_skills);

  // Detected
  doc.setFontSize(FONT_H2);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...DARK);
  doc.text("Detected Skills", MARGIN, y);
  y += 5;

  if (detected.length === 0) {
    doc.setFontSize(FONT_BODY);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(...GRAY);
    doc.text("No detected skills found.", MARGIN, y);
    y += 8;
  } else {
    const rows = detected.map((s, i) => [i + 1, typeof s === "string" ? s : s.skill || JSON.stringify(s)]);
    y = tableTheme(doc, y, [["#", "Skill"]], rows, {
      0: { cellWidth: 12 },
      1: { cellWidth: "auto" },
    });
  }

  y = ensureSpace(doc, y, 30);

  // Missing
  doc.setFontSize(FONT_H2);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...DARK);
  doc.text("Missing Skills", MARGIN, y);
  y += 5;

  if (missing.length === 0) {
    doc.setFontSize(FONT_BODY);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(...GRAY);
    doc.text("No missing skills identified.", MARGIN, y);
    y += 8;
  } else {
    const rows = missing.map((s, i) => [i + 1, typeof s === "string" ? s : s.skill || JSON.stringify(s)]);
    y = tableTheme(doc, y, [["#", "Skill"]], rows, {
      0: { cellWidth: 12 },
      1: { cellWidth: "auto" },
    });
  }

  return y;
}

/** Trending market skills */
function drawTrendingSkills(doc, report, startY) {
  let y = ensureSpace(doc, startY, 40);
  if (y < 25) y = 22;

  y = sectionHeading(doc, "Trending Market Skills", y);
  hrule(doc, y);
  y += 8;

  const skills = toArr(report.trending_skills);

  if (skills.length === 0) {
    doc.setFontSize(FONT_BODY);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(...GRAY);
    doc.text("No trending skills data available.", MARGIN, y);
    return y + 8;
  }

  const rows = skills.map((s) => {
    const name   = typeof s === "string" ? s : (s.skill || s.name || "—");
    const demand = typeof s === "object" && s.demand_pct != null ? `${s.demand_pct}%` : "—";
    return [name, demand];
  });

  return tableTheme(doc, y,
    [["Skill", "Demand %"]],
    rows,
    {
      0: { cellWidth: "auto" },
      1: { cellWidth: 30, halign: "center" },
    }
  );
}

/** Career role alignments */
function drawRoleAlignments(doc, report, startY) {
  let y = ensureSpace(doc, startY, 40);
  if (y < 25) y = 22;

  y = sectionHeading(doc, "Career Role Alignment", y);
  hrule(doc, y);
  y += 8;

  const roles = toArr(report.role_alignments);

  if (roles.length === 0) {
    doc.setFontSize(FONT_BODY);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(...GRAY);
    doc.text("No role alignment data available.", MARGIN, y);
    return y + 8;
  }

  const rows = roles.map((r) => [
    r.role || "—",
    r.alignment_pct != null ? `${r.alignment_pct}%` : "—",
  ]);

  return tableTheme(doc, y,
    [["Role", "Alignment %"]],
    rows,
    {
      0: { cellWidth: "auto" },
      1: { cellWidth: 35, halign: "center" },
    }
  );
}

/** Learning roadmap */
function drawRoadmap(doc, report, startY) {
  let y = ensureSpace(doc, startY, 40);
  if (y < 25) y = 22;

  y = sectionHeading(doc, "Learning Roadmap", y);
  hrule(doc, y);
  y += 8;

  const roadmap = toArr(report.roadmap);

  if (roadmap.length === 0) {
    doc.setFontSize(FONT_BODY);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(...GRAY);
    doc.text("No roadmap data available.", MARGIN, y);
    return y + 8;
  }

  const rows = roadmap.map((item) => [
    item.week      ?? "—",
    item.skill     ?? "—",
    item.priority  ?? "—",
    item.duration  ?? "—",
  ]);

  return tableTheme(doc, y,
    [["Week", "Skill", "Priority", "Duration"]],
    rows,
    {
      0: { cellWidth: 18, halign: "center" },
      1: { cellWidth: "auto" },
      2: { cellWidth: 28, halign: "center" },
      3: { cellWidth: 30, halign: "center" },
    }
  );
}

// ─── Main export function ─────────────────────────────────────────────────────

/**
 * Generate and download a career report PDF.
 * @param {object} report - The full report object from the API.
 */
export function exportCareerReportPDF(report) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });

  // Cover
  drawCover(doc, report);

  // Summary
  let y = drawSummary(doc, report);

  // Skills
  y = drawSkills(doc, report, y);

  // Trending Skills
  y = drawTrendingSkills(doc, report, y);

  // Role Alignments
  y = drawRoleAlignments(doc, report, y);

  // Roadmap
  drawRoadmap(doc, report, y);

  // Footers on every page
  addFooters(doc);

  // Download
  const safeName = (report.candidate_name || "candidate")
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");
  doc.save(`career_report_${safeName}_${Date.now()}.pdf`);
}
