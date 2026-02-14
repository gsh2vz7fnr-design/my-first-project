import React from "react";
import { SlideContent } from "../../types/dsl";

type Props = {
  content: SlideContent;
  themeOverride?: Record<string, unknown> | null;
};

export function ThreeColumnPoints({ content }: Props) {
  const points = (content.bullets || []).slice(0, 3);
  return (
    <section style={{ height: "100%", padding: 28, background: "#FCFDFF" }}>
      <h2 style={{ margin: 0, fontSize: 42 }}>{content.title || "三点总结"}</h2>
      <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
        {points.map((item, idx) => (
          <article
            key={`${idx}-${item}`}
            style={{
              border: "1px solid #dbeafe",
              borderRadius: 16,
              background: "#F8FAFF",
              padding: 18,
              minHeight: 250,
            }}
          >
            <div style={{ fontSize: 13, color: "#1d4ed8", marginBottom: 10 }}>要点 {idx + 1}</div>
            <p style={{ margin: 0, fontSize: 21, lineHeight: 1.35, color: "#0f172a" }}>{item}</p>
          </article>
        ))}
      </div>
      <small style={{ display: "block", marginTop: 16, color: "#64748b" }}>{content.footer || ""}</small>
    </section>
  );
}
