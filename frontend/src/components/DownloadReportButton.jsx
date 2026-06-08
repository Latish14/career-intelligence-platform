import { useState } from "react";
import { exportCareerReportPDF } from "../utils/pdfExport";

/**
 * DownloadReportButton
 * Drop this anywhere you have access to the `report` object.
 * Props:
 *   report  – the full report object
 *   className – optional extra CSS class
 */
function DownloadReportButton({ report, className = "" }) {
  const [loading, setLoading] = useState(false);

  async function handleDownload() {
    if (!report || loading) return;
    setLoading(true);
    try {
      // jsPDF is synchronous but wrapping keeps UI responsive
      await Promise.resolve();
      exportCareerReportPDF(report);
    } catch (err) {
      console.error("PDF export failed:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      className={`download-report-btn ${className}`}
      onClick={handleDownload}
      disabled={loading || !report}
      aria-label="Download career report as PDF"
    >
      {loading ? (
        <>
          <span className="download-report-btn__spinner" aria-hidden="true" />
          Generating PDF…
        </>
      ) : (
        <>
          <svg
            className="download-report-btn__icon"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
          Download Career Report
        </>
      )}
    </button>
  );
}

export default DownloadReportButton;
