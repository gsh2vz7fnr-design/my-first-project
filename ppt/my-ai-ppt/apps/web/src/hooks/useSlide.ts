import { useEffect, useMemo, useState } from "react";
import { Slide } from "../types/dsl";

export function useSlide(slide: Slide | null) {
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [body, setBody] = useState("");
  const [footer, setFooter] = useState("");

  useEffect(() => {
    setTitle(slide?.content?.title || "");
    setSubtitle(slide?.content?.subtitle || "");
    setBody(slide?.content?.body || "");
    setFooter(slide?.content?.footer || "");
  }, [slide?.slide_id, slide?.content?.title, slide?.content?.subtitle, slide?.content?.body, slide?.content?.footer]);

  const dirty = useMemo(() => {
    if (!slide) return false;
    return (
      title !== (slide.content.title || "") ||
      subtitle !== (slide.content.subtitle || "") ||
      body !== (slide.content.body || "") ||
      footer !== (slide.content.footer || "")
    );
  }, [body, footer, slide, subtitle, title]);

  return {
    title,
    setTitle,
    subtitle,
    setSubtitle,
    body,
    setBody,
    footer,
    setFooter,
    dirty,
  };
}
