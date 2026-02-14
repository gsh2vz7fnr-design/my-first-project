import { ExportSummary, ProjectDSL, PromptConfig, PromptVersionSummary, SnapshotSummary, TaskSummary } from "../types/dsl";
export const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function createProject(sourceText: string) {
  return request<{ project_id: string; created_at: string }>("/api/v1/projects/", {
    method: "POST",
    body: JSON.stringify({ title: "Demo Project", source_text: sourceText }),
  });
}

export async function generateDsl(projectId: string, force = false) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/dsl`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export async function updateProjectSource(projectId: string, sourceText: string) {
  return request<{ ok: boolean }>(`/api/v1/projects/${projectId}/source`, {
    method: "PUT",
    body: JSON.stringify({ source_text: sourceText }),
  });
}

export async function getDsl(projectId: string) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/dsl`);
}

export type UpdateSlidePatch = {
  title?: string;
  subtitle?: string;
  body?: string;
  footer?: string;
};

export async function updateSlide(projectId: string, slideId: string, patch: UpdateSlidePatch) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/slides/${slideId}`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export async function regenerateSlide(
  projectId: string,
  slideId: string,
  userInstruction: string,
  lockedFields: string[]
) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/slides/${slideId}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ user_instruction: userInstruction, locked_fields: lockedFields }),
  });
}

export async function addSlide(projectId: string, afterSlideId: string | null, layoutId: string, pageType = "content") {
  return request<{ dsl: ProjectDSL; slide_id: string }>(`/api/v1/projects/${projectId}/slides`, {
    method: "POST",
    body: JSON.stringify({ after_slide_id: afterSlideId, layout_id: layoutId, page_type: pageType }),
  });
}

export async function deleteSlide(projectId: string, slideId: string) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/slides/${slideId}`, {
    method: "DELETE",
  });
}

export async function reorderSlides(projectId: string, slideIds: string[]) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/slides/reorder`, {
    method: "POST",
    body: JSON.stringify({ slide_ids: slideIds }),
  });
}

export async function updateSlideLayout(projectId: string, slideId: string, layoutId: string) {
  return request<{ dsl: ProjectDSL }>(`/api/v1/projects/${projectId}/slides/${slideId}/layout`, {
    method: "PUT",
    body: JSON.stringify({ layout_id: layoutId }),
  });
}

export async function createSnapshot(projectId: string) {
  return request<{ snapshot_id: string; created_at: string }>(`/api/v1/projects/${projectId}/snapshots`, {
    method: "POST",
  });
}

export async function listSnapshots(projectId: string) {
  return request<{ items: SnapshotSummary[] }>(`/api/v1/projects/${projectId}/snapshots`);
}

export async function restoreSnapshot(projectId: string, snapshotId: string) {
  return request<{ dsl: ProjectDSL; snapshot_id: string }>(`/api/v1/projects/${projectId}/restore/${snapshotId}`, {
    method: "POST",
  });
}

export async function createPptxExport(projectId: string, mode: "editable_text" | "image_fallback" = "editable_text") {
  return request<{ item: ExportSummary }>(`/api/v1/projects/${projectId}/exports/pptx`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function listExports(projectId: string) {
  return request<{ items: ExportSummary[] }>(`/api/v1/projects/${projectId}/exports`);
}

export async function getCurrentPrompts() {
  return request<{ item: PromptConfig }>("/api/v1/prompts/current");
}

export async function updateCurrentPrompts(outlinePrompt: string, detailPrompt: string, note: string) {
  return request<{ item: PromptConfig }>("/api/v1/prompts/current", {
    method: "PUT",
    body: JSON.stringify({ outline_prompt: outlinePrompt, detail_prompt: detailPrompt, note }),
  });
}

export async function listPromptHistory() {
  return request<{ items: PromptVersionSummary[] }>("/api/v1/prompts/history");
}

export async function restorePromptVersion(version: number) {
  return request<{ item: PromptConfig }>("/api/v1/prompts/restore", {
    method: "POST",
    body: JSON.stringify({ version }),
  });
}

export async function createGenerateDslTask(projectId: string, force = true) {
  return request<{ item: TaskSummary }>(`/api/v1/projects/${projectId}/tasks/generate-dsl`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export async function createExportTask(projectId: string, mode: "editable_text" | "image_fallback" = "editable_text") {
  return request<{ item: TaskSummary }>(`/api/v1/projects/${projectId}/tasks/export-pptx`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function getTask(projectId: string, taskId: string) {
  return request<{ item: TaskSummary }>(`/api/v1/projects/${projectId}/tasks/${taskId}`);
}
