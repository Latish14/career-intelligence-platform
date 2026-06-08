import { Download, Loader2, CheckCircle } from "lucide-react";

export default function DownloadButton({ downloadStatus, progress, onClick }) {
  const isIdle = downloadStatus === "idle";
  const isGenerating = downloadStatus === "generating";
  const isSuccess = downloadStatus === "success";

  return (
    <button
      onClick={onClick}
      disabled={!isIdle}
      className={`download-btn ${isGenerating ? "download-btn--generating" : ""} ${
        isSuccess ? "download-btn--success" : ""
      }`}
      aria-label="Download career report as PDF"
    >
      <div className="download-btn__content">
        {isIdle && <Download className="download-btn__icon" size={16} />}
        {isGenerating && <Loader2 className="download-btn__icon download-btn__icon--spin" size={16} />}
        {isSuccess && <CheckCircle className="download-btn__icon" size={16} />}
        
        <span className="download-btn__text">
          {isIdle && "Download Report"}
          {isGenerating && `Generating PDF... ${progress}%`}
          {isSuccess && "Downloaded"}
        </span>
      </div>
      
      {isGenerating && (
        <div className="download-btn__progress-bar">
          <div 
            className="download-btn__progress-fill" 
            style={{ width: `${progress}%` }} 
          />
        </div>
      )}
    </button>
  );
}
