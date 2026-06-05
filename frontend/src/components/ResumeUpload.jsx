import { useRef, useState } from "react";
import { uploadResume } from "../services/api";
import ReportDashboard from "./ReportDashboard";
import LoadingOverlay from "./LoadingOverlay";
import ErrorBoundary from "./ErrorBoundary";
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ResumeUpload() {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const acceptTypes = [".pdf", ".doc", ".docx"];

  const validateAndSetFile = (file) => {
    if (!file) return;

    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!acceptTypes.includes(extension)) {
      setError("Please upload a PDF, DOC, or DOCX file.");
      return;
    }

    setSelectedFile(file);
    setError("");
  };

  const handleFileChange = (event) => {
    validateAndSetFile(event.target.files?.[0] || null);
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
      setError(err.message || "Failed to upload resume.");
    } finally {
      setLoading(false);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    validateAndSetFile(event.dataTransfer.files?.[0] || null);
  };

  const handleReset = () => {
    setReport(null);
    setSelectedFile(null);
    setError("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <section
      className={`upload-section${report ? " upload-section--with-report" : ""}`}
    >
      {loading && <LoadingOverlay />}

      {!report && (
        <div className="upload-hero animate-fade-in">
          <span className="upload-hero__eyebrow">Career Intelligence</span>
          <h1 className="upload-hero__title">Analyze Your Career Potential</h1>
          <p className="upload-hero__description">
            Upload your resume to receive a comprehensive intelligence report
            with skill analysis, market trends, and a personalized learning
            roadmap.
          </p>
        </div>
      )}

      <div
        className={`upload-card animate-fade-in${report ? " upload-card--compact" : ""}`}
      >
        <div
          className={`upload-card__dropzone${
            selectedFile ? " upload-card__dropzone--active" : ""
          }${isDragging ? " upload-card__dropzone--dragging" : ""}`}
          onClick={handleBrowseClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onKeyDown={(e) => e.key === "Enter" && handleBrowseClick()}
          role="button"
          tabIndex={0}
          aria-label="Upload resume file"
        >
          <div className="upload-card__icon" aria-hidden="true">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>

          <p className="upload-card__label">
            {isDragging ? "Drop your resume here" : "Drag & drop your resume"}
          </p>
          <p className="upload-card__hint">
            PDF, DOC, or DOCX — max 10 MB
          </p>

          <input
            ref={fileInputRef}
            id="resume-file"
            className="upload-card__input"
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={handleFileChange}
          />

          {!selectedFile && (
            <span className="upload-card__browse">Browse files</span>
          )}

          {selectedFile && (
            <div
              className="upload-card__file"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="upload-card__file-icon" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <div className="upload-card__file-info">
                <span className="upload-card__file-name">
                  {selectedFile.name}
                </span>
                <span className="upload-card__file-size">
                  {formatFileSize(selectedFile.size)}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="upload-card__actions">
          {!report ? (
            <button
              type="button"
              className="btn btn--primary"
              onClick={handleUpload}
              disabled={loading || !selectedFile}
            >
              {loading ? "Generating Report..." : "Generate Career Report"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={handleReset}
            >
              Upload another resume
            </button>
          )}
        </div>

        {error && (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        )}
      </div>

      {report && (
        <ErrorBoundary onReset={handleReset}>
          <ReportDashboard report={report} />
        </ErrorBoundary>
      )}    </section>
  );
}

export default ResumeUpload;
