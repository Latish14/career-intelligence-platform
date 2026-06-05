function LoadingOverlay() {
  return (
    <div
      className="loading-overlay"
      role="status"
      aria-live="polite"
      aria-label="Generating career intelligence report"
    >
      <div className="loading-overlay__content">
        <div className="loading-overlay__ring">
          <div className="loading-overlay__ring-pulse" />
          <svg className="loading-overlay__ring-svg" viewBox="0 0 80 80">
            <defs>
              <linearGradient id="loaderGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#a5b4fc" />
                <stop offset="50%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#6366f1" />
              </linearGradient>
            </defs>
            <circle className="loading-overlay__ring-track" cx="40" cy="40" r="35" />
            <circle className="loading-overlay__ring-progress" cx="40" cy="40" r="35" />
          </svg>
          <div className="loading-overlay__ring-spinner" />
        </div>

        <h2 className="loading-overlay__title">
          Generating Career Intelligence Report
        </h2>

        <p className="loading-overlay__subtitle">
          Analyzing your skills and market opportunities
        </p>
      </div>
    </div>
  );
}

export default LoadingOverlay;
