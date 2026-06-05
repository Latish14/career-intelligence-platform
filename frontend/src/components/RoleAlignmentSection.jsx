function RoleAlignmentSection({
  roles = [],
}) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: "12px",
        padding: "1.5rem",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
      }}
    >
      <h2
        style={{
          textAlign: "center",
          marginBottom: "1rem",
        }}
      >
        🎯 Career Role Alignment
      </h2>

      {roles.length === 0 ? (
        <p style={{ textAlign: "center" }}>
          No alignment data available.
        </p>
      ) : (
        roles.map((role, index) => (
          <div
            key={index}
            style={{
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>{role.role}</span>

              <span>
                {role.alignment_pct}%
              </span>
            </div>

            <div
              style={{
                width: "100%",
                height: "10px",
                background: "#e5e7eb",
                borderRadius: "999px",
              }}
            >
              <div
                style={{
                  width: `${role.alignment_pct}%`,
                  height: "100%",
                  background: "#10b981",
                  borderRadius: "999px",
                }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default RoleAlignmentSection;