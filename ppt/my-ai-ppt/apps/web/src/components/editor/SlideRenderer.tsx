import React from "react";
import { LayoutRegistry } from "../layouts/registry";
import { Slide } from "../../types/dsl";

export function SlideRenderer({ slide }: { slide: Slide }) {
  const Layout = LayoutRegistry[slide.layout_id] || LayoutRegistry.default;
  return <Layout content={slide.content} themeOverride={slide.theme_override} />;
}
