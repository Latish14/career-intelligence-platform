// frontend/src/components/RoadmapSection.jsx

function RoadmapSection({ roadmap = [] }) {
  const hasRoadmap =
    Array.isArray(roadmap) && roadmap.length > 0;

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
          marginBottom: "1.5rem",
        }}
      >
        Learning Roadmap
      </h3>

      {!hasRoadmap ? (
        <p
          style={{
            margin: 0,
            color: "#6b7280",
          }}
        >
          No roadmap available.
        </p>
      ) : (
        <div
          style={{
            position: "relative",
            display: "flex",
            flexDirection: "column",
            gap: "1.5rem",
          }}
        >
          {roadmap.map((item, index) => (
            <div
              key={`${item.skill}-${item.week}-${index}`}
              style={{
                display: "flex",
                gap: "1rem",
                alignItems: "flex-start",
              }}
            >
              {/* Timeline Marker */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    width: "16px",
                    height: "16px",
                    borderRadius: "50%",
                    border: "2px solid #2563eb",
                    background: "#ffffff",
                  }}
                />

                {index < roadmap.length - 1 && (
                  <div
                    style={{
                      width: "2px",
                      height: "100%",
                      minHeight: "80px",
                      background: "#d1d5db",
                      marginTop: "4px",
                    }}
                  />
                )}
              </div>

              {/* Content Card */}
              <div
                style={{
                  flex: 1,
                  border: "1px solid #e5e7eb",
                  borderRadius: "10px",
                  padding: "1rem",
                  background: "#f9fafb",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "0.75rem",
                    marginBottom: "0.75rem",
                  }}
                >
                  <span
                    style={{
                      padding: "0.25rem 0.75rem",
                      borderRadius: "999px",
                      background: "#eef2ff",
                      fontSize: "0.85rem",
                      fontWeight: "600",
                    }}
                  >
                    Week {item.week}
                  </span>

                  <span
                    style={{
                      padding: "0.25rem 0.75rem",
                      borderRadius: "999px",
                      background: "#f3f4f6",
                      fontSize: "0.85rem",
                    }}
                  >
                    {item.priority} Priority
                  </span>

                  <span
                    style={{
                      padding: "0.25rem 0.75rem",
                      borderRadius: "999px",
                      background: "#f3f4f6",
                      fontSize: "0.85rem",
                    }}
                  >
                    {item.category}
                  </span>
                </div>

                <h4
                  style={{
                    margin: 0,
                    marginBottom: "0.5rem",
                  }}
                >
                  {item.skill}
                </h4>

                <p
                  style={{
                    margin: 0,
                    marginBottom: "0.75rem",
                    color: "#4b5563",
                    lineHeight: 1.5,
                  }}
                >
                  {item.reason}
                </p>

                <div
                  style={{
                    fontSize: "0.9rem",
                    color: "#6b7280",
                  }}
                >
                  Duration:{" "}
                  <strong>
                    {item.duration_weeks} week
                    {item.duration_weeks > 1 ? "s" : ""}
                  </strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default RoadmapSection;
