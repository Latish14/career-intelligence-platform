// frontend/src/components/ReportSummary.jsx

function ReportSummary({
  candidateName,
  targetRole,
  placementScore,
  coveragePct,
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        padding: "1.5rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        width: "100%",
        maxWidth: "900px",
        margin: "0 auto",
      }}
    >
      <h2
        style={{
          margin: 0,
          marginBottom: "1rem",
        }}
      >
        Report Overview
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
        }}
      >
        <div>
          <p
            style={{
              margin: 0,
              color: "#6b7280",
              fontSize: "0.9rem",
            }}
          >
            Candidate
          </p>

          <h3
            style={{
              marginTop: "0.25rem",
            }}
          >
            {candidateName}
          </h3>
        </div>

        <div>
          <p
            style={{
              margin: 0,
              color: "#6b7280",
              fontSize: "0.9rem",
            }}
          >
            Target Role
          </p>

          <h3
            style={{
              marginTop: "0.25rem",
            }}
          >
            {targetRole}
          </h3>
        </div>

        <div>
          <p
            style={{
              margin: 0,
              color: "#6b7280",
              fontSize: "0.9rem",
            }}
          >
            Skill Coverage
          </p>

          <h3
            style={{
              marginTop: "0.25rem",
            }}
          >
            {coveragePct}%
          </h3>
        </div>
      </div>

      <div
        style={{
          marginTop: "1.5rem",
          padding: "1.5rem",
          borderRadius: "10px",
          textAlign: "center",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
        }}
      >
        <p
          style={{
            margin: 0,
            color: "#6b7280",
            fontSize: "0.95rem",
          }}
        >
          Placement Score
        </p>

        <div
          style={{
            fontSize: "3rem",
            fontWeight: "700",
            lineHeight: 1.1,
            marginTop: "0.5rem",
          }}
        >
          {placementScore}
        </div>

        <p
          style={{
            marginTop: "0.5rem",
            color: "#6b7280",
          }}
        >
          out of 100
        </p>
      </div>
    </div>
  );
}

export default ReportSummary;
