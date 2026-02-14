export type SlideContent = {
  title?: string;
  subtitle?: string;
  body?: string;
  footer?: string;
  bullets: string[];
  image_src?: string | null;
};

export type Slide = {
  slide_id: string;
  page_type: string;
  layout_id: string;
  theme_override?: Record<string, unknown> | null;
  content: SlideContent;
  constraints: Record<string, unknown>;
};

export type ProjectDSL = {
  project_id: string;
  theme: Record<string, unknown>;
  slides: Slide[];
};

export type SnapshotSummary = {
  snapshot_id: string;
  created_at: string;
};

export type ExportSummary = {
  job_id: string;
  mode: "editable_text" | "image_fallback";
  status: string;
  download_path?: string | null;
  download_url?: string | null;
  created_at: string;
  updated_at: string;
};

export type PromptConfig = {
  version: string;
  outline_prompt: string;
  detail_prompt: string;
};

export type PromptVersionSummary = {
  version: number;
  note: string;
  created_at: string;
};

export type TaskSummary = {
  task_id: string;
  task_type: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  message: string;
  error?: string | null;
  result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};
