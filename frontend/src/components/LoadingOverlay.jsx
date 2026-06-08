function LoadingOverlay() {
  return (
    <div
      className="loading-overlay"
      role="status"
      aria-live="polite"
      aria-label="Generating career intelligence report"
    >
      <div className="loading-overlay__content">
        <div className="morph-loader">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className={`morph-square morph-square-${i}`}
            />
          ))}
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
