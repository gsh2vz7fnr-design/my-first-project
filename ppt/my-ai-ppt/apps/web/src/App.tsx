import React, { useEffect, useMemo, useState } from "react";
import {
  addSlide,
  apiBase,
  createExportTask,
  createProject,
  createGenerateDslTask,
  deleteSlide,
  generateDsl,
  getTask,
  getCurrentPrompts,
  getDsl,
  listExports,
  listPromptHistory,
  regenerateSlide,
  reorderSlides,
  restorePromptVersion,
  updateCurrentPrompts,
  updateProjectSource,
  updateSlideLayout,
  updateSlide,
} from "./api/client";
import { SlideRenderer } from "./components/editor/SlideRenderer";
import { useHistory } from "./hooks/useHistory";
import { useSlide } from "./hooks/useSlide";
import { ExportSummary, ProjectDSL, PromptVersionSummary, TaskSummary } from "./types/dsl";

const PROJECT_KEY = "my_ai_ppt_project_id";
const SOURCE_KEY = "my_ai_ppt_source_text";

export default function App() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [dsl, setDsl] = useState<ProjectDSL | null>(null);
  const [slideIndex, setSlideIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [exports, setExports] = useState<ExportSummary[]>([]);
  const [sourceText, setSourceText] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);
  const [outlinePrompt, setOutlinePrompt] = useState("");
  const [detailPrompt, setDetailPrompt] = useState("");
  const [promptVersion, setPromptVersion] = useState("-");
  const [promptNote, setPromptNote] = useState("manual update");
  const [promptHistory, setPromptHistory] = useState<PromptVersionSummary[]>([]);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [slideInstruction, setSlideInstruction] = useState("");
  const [regeneratingSlide, setRegeneratingSlide] = useState(false);
  const [layoutId, setLayoutId] = useState("cover_centered_01");
  const [lockFields, setLockFields] = useState<Record<string, boolean>>({
    title: false,
    subtitle: false,
    body: false,
    footer: false,
    bullets: false,
  });

  const slide = useMemo(() => dsl?.slides?.[slideIndex], [dsl, slideIndex]);
  const { title, setTitle, subtitle, setSubtitle, body, setBody, footer, setFooter, dirty } = useSlide(slide || null);
  const { snapshots, loadingSnapshots, refreshSnapshots, create, restore } = useHistory(projectId, setDsl);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        let pid = localStorage.getItem(PROJECT_KEY);
        const initialText = localStorage.getItem(SOURCE_KEY) || "AI 助力内容生产\n从文档到可编辑演示";
        if (!pid) {
          const created = await createProject(initialText);
          pid = created.project_id;
          localStorage.setItem(PROJECT_KEY, pid);
        }
        setProjectId(pid);
        setSourceText(localStorage.getItem(SOURCE_KEY) || "");

        try {
          const current = await getDsl(pid);
          setDsl(current.dsl);
        } catch (err: any) {
          const msg = String(err?.message || "");
          if (msg.includes("project not found")) {
            const recreated = await createProject(initialText);
            localStorage.setItem(PROJECT_KEY, recreated.project_id);
            setProjectId(recreated.project_id);
            const generated = await generateDsl(recreated.project_id, true);
            setDsl(generated.dsl);
          } else {
            const generated = await generateDsl(pid);
            setDsl(generated.dsl);
          }
        }
        setError(null);
      } catch (e: any) {
        setError(e?.message || "初始化失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (projectId) {
      refreshSnapshots().catch((err: Error) => setError(err.message));
      listExports(projectId)
        .then((res) => setExports(res.items))
        .catch((err: Error) => setError(err.message));
    }
  }, [projectId, refreshSnapshots]);

  useEffect(() => {
    getCurrentPrompts()
      .then((res) => {
        setOutlinePrompt(res.item.outline_prompt);
        setDetailPrompt(res.item.detail_prompt);
        setPromptVersion(res.item.version);
      })
      .catch((err: Error) => setError(err.message));
    listPromptHistory()
      .then((res) => setPromptHistory(res.items))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!dsl?.slides?.length) {
      setSlideIndex(0);
      return;
    }
    if (slideIndex > dsl.slides.length - 1) {
      setSlideIndex(dsl.slides.length - 1);
    }
  }, [dsl, slideIndex]);

  useEffect(() => {
    setSlideInstruction("");
    setLayoutId(slide?.layout_id || "cover_centered_01");
  }, [slide?.slide_id]);

  const onSave = async () => {
    if (!projectId || !slide) return;
    setSaving(true);
    try {
      const updated = await updateSlide(projectId, slide.slide_id, { title, subtitle, body, footer });
      setDsl(updated.dsl);
      setNotice("已保存");
      setTimeout(() => setNotice(null), 1200);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onSnapshot = async () => {
    try {
      await create();
      setNotice("快照已创建");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "创建快照失败");
    }
  };

  const onRestore = async (snapshotId: string) => {
    try {
      await restore(snapshotId);
      setNotice("已恢复到该快照");
      setTimeout(() => setNotice(null), 1200);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "恢复失败");
    }
  };

  const onExport = async () => {
    if (!projectId) return;
    try {
      const createdTask = await createExportTask(projectId, "editable_text");
      setActiveTask(createdTask.item);
      let currentTask = createdTask.item;
      for (let i = 0; i < 60; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const polled = await getTask(projectId, currentTask.task_id);
        currentTask = polled.item;
        setActiveTask(currentTask);
        if (currentTask.status === "completed" || currentTask.status === "failed") {
          break;
        }
      }
      if (currentTask.status === "failed") {
        throw new Error(currentTask.error || "导出任务失败");
      }
      const latest = await listExports(projectId);
      setExports(latest.items);
      const latestItem = latest.items[0];
      setNotice(`导出完成: ${latestItem?.download_path || latestItem?.job_id || ""}`);
      setTimeout(() => setNotice(null), 2000);
    } catch (e: any) {
      setError(e?.message || "导出失败");
    }
  };

  const onSaveSource = async () => {
    if (!projectId) return;
    try {
      await updateProjectSource(projectId, sourceText);
      localStorage.setItem(SOURCE_KEY, sourceText);
      setNotice("文档已保存");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "保存文档失败");
    }
  };

  const onRegenerate = async () => {
    if (!projectId) return;
    setRegenerating(true);
    try {
      await updateProjectSource(projectId, sourceText);
      localStorage.setItem(SOURCE_KEY, sourceText);
      const createdTask = await createGenerateDslTask(projectId, true);
      setActiveTask(createdTask.item);
      let currentTask = createdTask.item;
      for (let i = 0; i < 60; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const polled = await getTask(projectId, currentTask.task_id);
        currentTask = polled.item;
        setActiveTask(currentTask);
        if (currentTask.status === "completed" || currentTask.status === "failed") {
          break;
        }
      }
      if (currentTask.status === "failed") {
        throw new Error(currentTask.error || "生成任务失败");
      }
      const rebuilt = await getDsl(projectId);
      setDsl(rebuilt.dsl);
      setSlideIndex(0);
      setNotice("已按文档重新生成");
      setTimeout(() => setNotice(null), 1600);
    } catch (e: any) {
      setError(e?.message || "重新生成失败");
    } finally {
      setRegenerating(false);
    }
  };

  const onSavePrompts = async () => {
    setSavingPrompt(true);
    try {
      const res = await updateCurrentPrompts(outlinePrompt, detailPrompt, promptNote || "manual update");
      setPromptVersion(res.item.version);
      const history = await listPromptHistory();
      setPromptHistory(history.items);
      setNotice(`提示词已保存为 v${res.item.version}`);
      setTimeout(() => setNotice(null), 1500);
    } catch (e: any) {
      setError(e?.message || "保存提示词失败");
    } finally {
      setSavingPrompt(false);
    }
  };

  const onRestorePrompt = async (version: number) => {
    try {
      const res = await restorePromptVersion(version);
      setOutlinePrompt(res.item.outline_prompt);
      setDetailPrompt(res.item.detail_prompt);
      setPromptVersion(res.item.version);
      const history = await listPromptHistory();
      setPromptHistory(history.items);
      setNotice(`已回滚并生成 v${res.item.version}`);
      setTimeout(() => setNotice(null), 1500);
    } catch (e: any) {
      setError(e?.message || "回滚提示词失败");
    }
  };

  const onRegenerateCurrentSlide = async () => {
    if (!projectId || !slide) return;
    if (!slideInstruction.trim()) {
      setError("请先输入你想改这页的内容要求");
      return;
    }
    setRegeneratingSlide(true);
    setError(null);
    try {
      const lockedFields = Object.keys(lockFields).filter((key) => lockFields[key]);
      const res = await regenerateSlide(projectId, slide.slide_id, slideInstruction.trim(), lockedFields);
      setDsl(res.dsl);
      setNotice("当前页已按意图重写");
      setTimeout(() => setNotice(null), 1500);
    } catch (e: any) {
      setError(e?.message || "重写当前页失败");
    } finally {
      setRegeneratingSlide(false);
    }
  };

  const onAddSlide = async () => {
    if (!projectId) return;
    try {
      const res = await addSlide(projectId, slide?.slide_id || null, layoutId, "content");
      setDsl(res.dsl);
      const idx = res.dsl.slides.findIndex((s) => s.slide_id === res.slide_id);
      if (idx >= 0) setSlideIndex(idx);
      setNotice("已新增页面");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "新增页面失败");
    }
  };

  const onDeleteSlide = async () => {
    if (!projectId || !slide) return;
    try {
      const res = await deleteSlide(projectId, slide.slide_id);
      setDsl(res.dsl);
      setSlideIndex((prev) => Math.max(0, Math.min(prev, res.dsl.slides.length - 1)));
      setNotice("已删除页面");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "删除页面失败");
    }
  };

  const onMoveSlide = async (dir: "prev" | "next") => {
    if (!projectId || !dsl?.slides?.length || !slide) return;
    const idx = dsl.slides.findIndex((s) => s.slide_id === slide.slide_id);
    if (idx < 0) return;
    const target = dir === "prev" ? idx - 1 : idx + 1;
    if (target < 0 || target >= dsl.slides.length) return;
    const ids = dsl.slides.map((s) => s.slide_id);
    [ids[idx], ids[target]] = [ids[target], ids[idx]];
    try {
      const res = await reorderSlides(projectId, ids);
      setDsl(res.dsl);
      setSlideIndex(target);
      setNotice("已调整页面顺序");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "调整顺序失败");
    }
  };

  const onChangeLayout = async (nextLayoutId: string) => {
    if (!projectId || !slide) return;
    setLayoutId(nextLayoutId);
    try {
      const res = await updateSlideLayout(projectId, slide.slide_id, nextLayoutId);
      setDsl(res.dsl);
      setNotice("布局已更新");
      setTimeout(() => setNotice(null), 1200);
    } catch (e: any) {
      setError(e?.message || "更新布局失败");
    }
  };

  if (loading) return <div style={{ padding: 24 }}>加载中...</div>;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", height: "100vh", overflow: "hidden" }}>
      <aside style={{ borderRight: "1px solid #e5e7eb", padding: 16, overflowY: "auto", height: "100vh" }}>
        <h3>编辑器</h3>
        <p style={{ fontSize: 12, color: "#6b7280" }}>项目: {projectId}</p>
        <p style={{ fontSize: 12, color: "#6b7280" }}>页面: {slide?.slide_id || "-"}</p>
        <p style={{ fontSize: 12, color: "#6b7280" }}>
          {dsl?.slides?.length ? `${slideIndex + 1}/${dsl.slides.length}` : "0/0"}
        </p>
        {error ? <p style={{ fontSize: 12, color: "crimson" }}>{error}</p> : null}
        {notice ? <p style={{ fontSize: 12, color: "#0f766e" }}>{notice}</p> : null}
        {activeTask ? (
          <p style={{ fontSize: 12, color: "#334155" }}>
            任务 {activeTask.task_type}: {activeTask.status} ({activeTask.progress}%){activeTask.message ? ` - ${activeTask.message}` : ""}
          </p>
        ) : null}
        <label style={{ display: "block", marginBottom: 8 }}>文档输入（支持粘贴长文本）</label>
        <textarea
          value={sourceText}
          onChange={(e) => setSourceText(e.target.value)}
          style={{ width: "100%", marginBottom: 8, minHeight: 120 }}
          placeholder="把文章粘贴到这里，然后点击“重新生成页面”"
        />
        <div style={{ marginBottom: 12 }}>
          <button onClick={onSaveSource} style={{ marginRight: 8 }}>保存文档</button>
          <button onClick={onRegenerate} disabled={regenerating}>
            {regenerating ? "生成中..." : "重新生成页面"}
          </button>
        </div>
        <details style={{ marginBottom: 12 }} open>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>本页修改意图</summary>
          <div style={{ marginTop: 8 }}>
            <textarea
              value={slideInstruction}
              onChange={(e) => setSlideInstruction(e.target.value)}
              style={{ width: "100%", minHeight: 72, marginBottom: 8 }}
              placeholder="例如：改得更口语化，适合家长；保留标题，正文改为3条要点"
            />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8, fontSize: 12 }}>
              {(
                [
                  { key: "title", label: "标题" },
                  { key: "subtitle", label: "副标题" },
                  { key: "body", label: "正文" },
                  { key: "footer", label: "页脚" },
                  { key: "bullets", label: "要点列表" },
                ] as const
              ).map((field) => (
                <label key={field.key} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <input
                    type="checkbox"
                    checked={lockFields[field.key]}
                    onChange={(e) => setLockFields((prev) => ({ ...prev, [field.key]: e.target.checked }))}
                  />
                  锁定{field.label}
                </label>
              ))}
            </div>
            <button onClick={onRegenerateCurrentSlide} disabled={regeneratingSlide}>
              {regeneratingSlide ? "重写中..." : "按意图重写本页"}
            </button>
          </div>
        </details>
        <details style={{ marginBottom: 12 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>提示词配置（当前 v{promptVersion}）</summary>
          <div style={{ marginTop: 8 }}>
            <label style={{ display: "block", marginBottom: 6 }}>大纲提示词（Outline）</label>
            <textarea value={outlinePrompt} onChange={(e) => setOutlinePrompt(e.target.value)} style={{ width: "100%", minHeight: 120, marginBottom: 8 }} />
            <label style={{ display: "block", marginBottom: 6 }}>单页提示词（Detail）</label>
            <textarea value={detailPrompt} onChange={(e) => setDetailPrompt(e.target.value)} style={{ width: "100%", minHeight: 120, marginBottom: 8 }} />
            <label style={{ display: "block", marginBottom: 6 }}>版本备注</label>
            <input value={promptNote} onChange={(e) => setPromptNote(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
            <button onClick={onSavePrompts} disabled={savingPrompt} style={{ marginBottom: 8 }}>
              {savingPrompt ? "保存中..." : "保存提示词版本"}
            </button>
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, maxHeight: 140, overflowY: "auto" }}>
              {promptHistory.length === 0 ? (
                <div style={{ padding: 8, fontSize: 12, color: "#6b7280" }}>暂无历史版本</div>
              ) : (
                promptHistory.map((item) => (
                  <div key={item.version} style={{ padding: "8px 10px", borderBottom: "1px solid #f1f5f9" }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>v{item.version} · {item.note}</div>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>{new Date(item.created_at).toLocaleString()}</div>
                    <button style={{ fontSize: 11 }} onClick={() => onRestorePrompt(item.version)}>回滚到此版本</button>
                  </div>
                ))
              )}
            </div>
          </div>
        </details>
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: "block", marginBottom: 6 }}>页面布局</label>
          <select
            value={layoutId}
            onChange={(e) => onChangeLayout(e.target.value)}
            style={{ width: "100%", marginBottom: 8 }}
          >
            <option value="cover_centered_01">封面居中</option>
            <option value="split_left_image_right_text">左图右文</option>
            <option value="three_column_points">三列要点</option>
          </select>
          <div style={{ marginBottom: 8 }}>
            <button onClick={onAddSlide} style={{ marginRight: 8 }}>新增页面</button>
            <button onClick={onDeleteSlide} disabled={!slide}>删除当前页</button>
          </div>
          <button onClick={() => setSlideIndex((prev) => Math.max(0, prev - 1))} disabled={slideIndex === 0} style={{ marginRight: 8 }}>
            上一页
          </button>
          <button
            onClick={() => setSlideIndex((prev) => Math.min((dsl?.slides?.length || 1) - 1, prev + 1))}
            disabled={!dsl?.slides?.length || slideIndex >= dsl.slides.length - 1}
            style={{ marginRight: 8 }}
          >
            下一页
          </button>
          <button onClick={() => onMoveSlide("prev")} disabled={slideIndex === 0} style={{ marginRight: 8 }}>
            上移
          </button>
          <button onClick={() => onMoveSlide("next")} disabled={!dsl?.slides?.length || slideIndex >= dsl.slides.length - 1}>
            下移
          </button>
        </div>
        <label style={{ display: "block", marginBottom: 8 }}>标题</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: "100%", marginBottom: 12 }} />
        <label style={{ display: "block", marginBottom: 8 }}>副标题</label>
        <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} style={{ width: "100%", marginBottom: 12 }} />
        <label style={{ display: "block", marginBottom: 8 }}>正文</label>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} style={{ width: "100%", marginBottom: 12, minHeight: 68 }} />
        <label style={{ display: "block", marginBottom: 8 }}>页脚</label>
        <input value={footer} onChange={(e) => setFooter(e.target.value)} style={{ width: "100%", marginBottom: 12 }} />
        <button onClick={onSave} disabled={!dirty || saving} style={{ marginRight: 8 }}>
          {saving ? "保存中..." : "保存页面"}
        </button>
        <button onClick={onSnapshot} style={{ marginRight: 8 }}>创建快照</button>
        <button onClick={onExport}>导出 PPTX</button>

        <hr style={{ margin: "16px 0" }} />
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong style={{ fontSize: 13 }}>快照</strong>
            <button onClick={() => refreshSnapshots()} disabled={loadingSnapshots}>
              {loadingSnapshots ? "..." : "刷新"}
            </button>
          </div>
          <div style={{ maxHeight: 240, overflowY: "auto", border: "1px solid #e5e7eb", borderRadius: 8 }}>
            {snapshots.length === 0 ? (
              <div style={{ padding: 12, fontSize: 12, color: "#6b7280" }}>暂无快照</div>
            ) : (
              snapshots.map((item) => (
                <button
                  key={item.snapshot_id}
                  onClick={() => onRestore(item.snapshot_id)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    border: "none",
                    borderBottom: "1px solid #f1f5f9",
                    background: "white",
                    padding: "10px 12px",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{item.snapshot_id}</div>
                  <div style={{ fontSize: 11, color: "#64748b" }}>{new Date(item.created_at).toLocaleString()}</div>
                </button>
              ))
            )}
          </div>
        </div>
        <hr style={{ margin: "16px 0" }} />
        <div>
          <strong style={{ fontSize: 13 }}>导出记录</strong>
          <div style={{ maxHeight: 160, overflowY: "auto", border: "1px solid #e5e7eb", borderRadius: 8, marginTop: 8 }}>
            {exports.length === 0 ? (
              <div style={{ padding: 12, fontSize: 12, color: "#6b7280" }}>暂无导出记录</div>
            ) : (
              exports.map((item) => (
                <div key={item.job_id} style={{ padding: "10px 12px", borderBottom: "1px solid #f1f5f9" }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{item.job_id}</div>
                  <div style={{ fontSize: 11, color: "#64748b" }}>
                    {item.status === "completed" ? "已完成" : item.status} | {item.mode === "editable_text" ? "可编辑文本" : "图片回退"}
                  </div>
                  <div style={{ fontSize: 11, color: "#334155", marginBottom: 6 }}>{item.download_path || "-"}</div>
                  {item.download_url ? (
                    <button
                      onClick={() => window.open(`${apiBase}${item.download_url}`, "_blank")}
                      style={{ fontSize: 11 }}
                    >
                      下载
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </aside>
      <main style={{ background: "#f3f4f6", padding: 24, overflow: "hidden", height: "100vh" }}>
        <div
          style={{
            width: 960,
            height: 540,
            background: "white",
            margin: "0 auto",
            borderRadius: 12,
            overflow: "hidden",
            position: "sticky",
            top: 24,
          }}
        >
          {slide ? <SlideRenderer slide={slide} /> : <div style={{ padding: 24 }}>暂无页面</div>}
        </div>
      </main>
    </div>
  );
}
