import React from "react";
import { SlideContent } from "../../types/dsl";

type Props = {
  content: SlideContent;
  themeOverride?: Record<string, unknown> | null;
};

export function SplitLeftImageRightText({ content }: Props) {
  return (
    <section style={{ display: "grid", gridTemplateColumns: "44% 56%", height: "100%", padding: 28, gap: 20 }}>
      <div
        style={{
          borderRadius: 18,
          background: "linear-gradient(160deg, #DBEAFE 0%, #EFF6FF 100%)",
          display: "grid",
          placeItems: "center",
          color: "#334155",
          fontSize: 14,
          border: "1px solid #dbeafe",
        }}
      >
        {content.image_src ? <img src={content.image_src} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : "图片槽位"}
      </div>
      <div style={{ padding: "8px 4px" }}>
        <h2 style={{ margin: 0, fontSize: 42, lineHeight: 1.2 }}>{content.title || "核心要点"}</h2>
        <p style={{ margin: "10px 0 18px", color: "#334155", fontSize: 20 }}>{content.subtitle || ""}</p>
        <ul style={{ margin: 0, paddingLeft: 22, color: "#0f172a", fontSize: 18, lineHeight: 1.5 }}>
          {(content.bullets || []).slice(0, 6).map((item, idx) => (
            <li key={`${idx}-${item}`} style={{ marginBottom: 8 }}>
              {item}
            </li>
          ))}
        </ul>
        <small style={{ display: "block", marginTop: 12, color: "#64748b" }}>{content.footer || ""}</small>
      </div>
    </section>
  );
}
