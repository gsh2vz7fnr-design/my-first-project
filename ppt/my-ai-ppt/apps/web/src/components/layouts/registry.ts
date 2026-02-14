import React from "react";
import { CoverCentered } from "./CoverCentered";
import { SplitLeftImageRightText } from "./SplitLeftImageRightText";
import { ThreeColumnPoints } from "./ThreeColumnPoints";
import { SlideContent } from "../../types/dsl";

type LayoutProps = {
  content: SlideContent;
  themeOverride?: Record<string, unknown> | null;
};

export const LayoutRegistry: Record<string, React.ComponentType<LayoutProps>> = {
  cover_centered_01: CoverCentered,
  split_left_image_right_text: SplitLeftImageRightText,
  three_column_points: ThreeColumnPoints,
  default: CoverCentered,
};
