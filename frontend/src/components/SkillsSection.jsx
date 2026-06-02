// frontend/src/components/SkillsSection.jsx

function SkillsSection({
  title,
  skills = [],
}) {
  const hasSkills =
    Array.isArray(skills) && skills.length > 0;

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        padding: "1.5rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        width: "100%",
      }}
    >
      <h3
        style={{
          margin: 0,
          marginBottom: "1rem",
        }}
      >
        {title}
      </h3>

      {!hasSkills ? (
        <p
          style={{
            margin: 0,
            color: "#6b7280",
          }}
        >
          No skills available.
        </p>
      ) : (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          {skills.map((item, index) => {
            const confidence =
              item?.confidence !== undefined &&
              item?.confidence !== null
                ? Math.round(item.confidence * 100)
                : null;

            return (
              <div
                key={`${item?.skill}-${index}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.6rem 0.9rem",
                  borderRadius: "999px",
                  border: "1px solid #d1d5db",
                  background: "#f9fafb",
                  fontSize: "0.95rem",
                  fontWeight: "500",
                }}
              >
                <span>
                  {item?.skill || "Unknown Skill"}
                </span>

                {confidence !== null && (
                  <span
                    style={{
                      fontSize: "0.8rem",
                      color: "#6b7280",
                      borderLeft:
                        "1px solid #d1d5db",
                      paddingLeft: "0.5rem",
                    }}
                  >
                    {confidence}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default SkillsSection;
