import React from "react";
import { SlideContent } from "../../types/dsl";

type Props = {
  content: SlideContent;
  themeOverride?: Record<string, unknown> | null;
};

export function CoverCentered({ content }: Props) {
  return (
    <section
      style={{
        display: "grid",
        placeItems: "center",
        height: "100%",
        padding: 32,
        background: "linear-gradient(135deg, #F7FAFF 0%, #EEF4FF 100%)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 900 }}>
        <h1 style={{ margin: "0 0 12px", fontSize: 56, lineHeight: 1.2 }}>{content?.title || "未命名标题"}</h1>
        <p style={{ margin: "0 0 24px", fontSize: 24, color: "#334155" }}>{content?.subtitle || ""}</p>
        <small style={{ color: "#64748b" }}>{content?.footer || ""}</small>
      </div>
    </section>
  );
}
