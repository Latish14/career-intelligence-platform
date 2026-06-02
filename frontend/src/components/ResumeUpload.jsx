// frontend/src/components/ResumeUpload.jsx

import { useState } from "react";
import { uploadResume } from "../services/api";
import ReportDashboard from "./ReportDashboard";

function ResumeUpload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (event) => {
    const file = event.target.files?.[0] || null;

    setSelectedFile(file);
    setError("");
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select a resume file.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setReport(null);

      const result = await uploadResume(selectedFile);

      setReport(result);
    } catch (err) {
      setError(
        err.message || "Failed to upload resume."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "2rem auto",
        padding: "1.5rem",
      }}
    >
      <h2>Career Intelligence Platform</h2>
      <p>Upload your resume to generate a career report.</p>

      <input
        type="file"
        accept=".pdf,.doc,.docx"
        onChange={handleFileChange}
      />

      <div style={{ marginTop: "1rem" }}>
        <button
          onClick={handleUpload}
          disabled={loading}
        >
          {loading
            ? "Generating Report..."
            : "Upload Resume"}
        </button>
      </div>

      {selectedFile && (
        <p style={{ marginTop: "1rem" }}>
          Selected File: {selectedFile.name}
        </p>
      )}

      {error && (
        <div
          style={{
            marginTop: "1rem",
            color: "red",
          }}
        >
          {error}
        </div>
      )}

      {report && (
        <ReportDashboard report={report} />
    )}
    </div>
  );
}

export default ResumeUpload;
