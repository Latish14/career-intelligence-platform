function TrendingSkillsSection({ skills = [] }) {
    console.log("TRENDING SKILLS:", skills);
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
        📈 Trending Market Skills
      </h2>

      {skills.length === 0 ? (
        <p style={{ textAlign: "center" }}>
          No trend data available.
        </p>
      ) : (
        skills.map((skill, index) => (
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
                marginBottom: "0.25rem",
              }}
            >
              <span>{skill.skill}</span>

              <span>
                {skill.demand_pct ?? 0}%
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
                  width: `${skill.demand_pct ?? 0}%`,
                  height: "100%",
                  background: "#2563eb",
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

export default TrendingSkillsSection;