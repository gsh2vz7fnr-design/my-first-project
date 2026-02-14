export type Slide = {
  slide_id: string;
  page_type: string;
  layout_id: string;
  theme_override?: Record<string, unknown> | null;
  content: {
    title?: string;
    subtitle?: string;
    body?: string;
    footer?: string;
    bullets?: string[];
    image_src?: string | null;
  };
  constraints?: Record<string, unknown>;
};

export type ProjectDSL = {
  project_id: string;
  theme: Record<string, unknown>;
  slides: Slide[];
};
