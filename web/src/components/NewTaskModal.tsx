import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { taskTemplate } from "../agentTemplates";
import type { DraftResult } from "../api";
import { api } from "../api";
import { useT } from "../i18n.tsx";
import type { Project, Task } from "../types";

export function NewTaskModal({ onClose, onCreated, project, task }: {
  onClose: () => void; onCreated: (t: Task) => void; project?: Project; task?: Task;
}) {
  const { t, locale } = useT();
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [instructions, setInstructions] = useState(task?.agent_instructions ?? "");
  const [projectInstructions, setProjectInstructions] = useState(project?.agent_instructions ?? "");
  const [criteria, setCriteria] = useState(task?.acceptance_criteria ?? "");
  const [tags, setTags] = useState(task?.tags.join(", ") ?? "");
  const [repo, setRepo] = useState(task?.repo_path ?? project?.repo_path ?? "");
  const [branch, setBranch] = useState(task?.base_branch ?? project?.default_branch ?? "");
  const [assigned, setAssigned] = useState(task?.assigned_to ?? "");
  const [agents, setAgents] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [screenshots, setScreenshots] = useState<Array<{ marker: string; file: File; preview: string; uploaded?: string }>>([]);
  const descriptionInput = useRef<HTMLTextAreaElement>(null);
  const previewUrls = useRef<string[]>([]);
  useEffect(() => () => { previewUrls.current.forEach(url => URL.revokeObjectURL(url)); }, []);
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [draftMode, setDraftMode] = useState<"spec" | "criteria">("spec");
  const [generating, setGenerating] = useState(false);
  async function generate(mode: "spec" | "criteria") {
    setGenerating(true); setError(""); setDraft(null); setDraftMode(mode);
    try {
      setDraft(await api.draftTask({ mode, title, description, acceptance_criteria: criteria, agent_instructions: instructions, project_instructions: projectInstructions, language: locale === "ru" ? "ru" : "en" }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setGenerating(false); }
  }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (task?.project_id) api.getProject(task.project_id).then(p => setProjectInstructions(p.agent_instructions)).catch(e => setError(String(e))); }, [task?.project_id]);
  // A persisted ID prevents duplicate task creation if an upload needs retrying.
  const [savedId, setSavedId] = useState<number | null>(task?.id ?? null);
  useEffect(() => { api.listTokens().then(tokens => setAgents([...new Set(tokens.map(tk => tk.agent_name))])).catch(() => {}); }, []);
  function pasteScreenshots(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    if (busy) return;
    const items = Array.from(e.clipboardData.items);
    const images = items.filter(item => item.kind === "file" && item.type.startsWith("image/"))
      .map(item => item.getAsFile()).filter((file): file is File => file !== null);
    if (!images.length) return; // Keep normal text paste unchanged.
    e.preventDefault();
    if (images.some(file => file.size > 20 * 1024 * 1024)) { setError(t("form.pasteTooLarge")); return; }
    setError("");
    const entries = images.map((file, index) => {
      const marker = `/__pending_screenshot__/${crypto.randomUUID()}`;
      const extension = file.type === "image/jpeg" ? "jpg" : file.type.split("/")[1].replace("+xml", "") || "png";
      const named = new File([file], `screenshot-${Date.now()}-${index}.${extension}`, { type: file.type });
      const preview = URL.createObjectURL(named);
      previewUrls.current.push(preview);
      return { marker, file: named, preview };
    });
    const start = e.currentTarget.selectionStart;
    const end = e.currentTarget.selectionEnd;
    const inserted = entries.map(image => `\n![${t("form.screenshot")}](${image.marker})\n`).join("");
    setScreenshots(previous => [...previous, ...entries]);
    setDescription(previous => previous.slice(0, start) + inserted + previous.slice(end));
    requestAnimationFrame(() => { descriptionInput.current?.setSelectionRange(start + inserted.length, start + inserted.length); });
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const persistedDescription = description.replace(/!\[[^\]]*\]\(\/__pending_screenshot__\/[a-z0-9-]+\)/g, "");
      const values = { title: title.trim(), description: persistedDescription, acceptance_criteria: criteria, agent_instructions: instructions, tags: tags.split(",").map(s => s.trim()).filter(Boolean), repo_path: repo.trim() || undefined, base_branch: branch.trim() || undefined, assigned_to: assigned || null };
      let result = savedId ? await api.updateTask(savedId, values) : await api.createTask({ ...values, project_id: project?.id });
      setSavedId(result.id);
      let resolvedDescription = description;
      for (const image of screenshots) {
        if (!resolvedDescription.includes(image.marker)) continue;
        const uploaded = image.uploaded ?? `/api/artifacts/${(await api.uploadAttachment(result.id, image.file)).id}/content`;
        // Cache successful uploads before PATCH so retries never duplicate images.
        setScreenshots(previous => previous.map(entry => entry.marker === image.marker ? { ...entry, uploaded } : entry));
        resolvedDescription = resolvedDescription.replaceAll(image.marker, uploaded);
        setDescription(previous => previous.replaceAll(image.marker, uploaded));
      }
      if (resolvedDescription !== persistedDescription) result = await api.updateTask(result.id, { description: resolvedDescription });
      // Remove each successful upload so retries don't create duplicate files.
      for (const file of files) { await api.uploadAttachment(result.id, file); setFiles(prev => prev.filter(f => f !== file)); }
      onCreated(result); onClose();
    } catch(e) { setError(e instanceof Error ? e.message : t("newTask.error")); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop">
    <form className="card modal task-modal" role="dialog" aria-modal="true" aria-labelledby="task-form-title" onClick={e => e.stopPropagation()} onSubmit={submit}>
      <div className="modal-heading"><div><div className="eyebrow">{project?.name ?? "AI Tasker"}</div><h2 id="task-form-title">{task ? t("form.editTask") : t("newTask.title")}</h2></div><button className="btn btn-ghost" type="button" disabled={busy} aria-label={t("common.close")} onClick={onClose}>×</button></div>
      <label>{t("newTask.titleLabel")}<input className="input" autoFocus required value={title} onChange={e => setTitle(e.target.value)} placeholder={t("newTask.titlePlaceholder")} /></label>
      <button className="btn" type="button" disabled={busy} onClick={() => { setDescription(previous => [previous, taskTemplate(locale)].filter(Boolean).join("\n\n")); if (!criteria) setCriteria(locale === "ru" ? "- [критерий 1]\n- [критерий 2]\n- [критерий 3]" : "- [criterion 1]\n- [criterion 2]\n- [criterion 3]"); }}>{t("instructions.taskTemplate")}</button>
      <label>{t("newTask.descLabel")}<textarea aria-label={t("newTask.descLabel")} ref={descriptionInput} className="input" rows={4} disabled={busy} onPaste={pasteScreenshots} value={description} onChange={e => setDescription(e.target.value)} placeholder={t("newTask.descPlaceholder")} /></label>
      <small className="muted">{t("form.pasteHint")}</small>
      <div className="form-actions">
        <button className="btn" type="button" disabled={busy || generating || !(title.trim() || description.trim())} onClick={() => generate("spec")}>{locale === "ru" ? "Подготовить ТЗ через OpenRouter" : "Draft specification with OpenRouter"}</button>
        <button className="btn" type="button" disabled={busy || generating || !(title.trim() || description.trim())} onClick={() => generate("criteria")}>{locale === "ru" ? "Сгенерировать критерии приёмки" : "Generate acceptance criteria"}</button>
      </div>
      {generating && <p role="status">{locale === "ru" ? "OpenRouter готовит предложение…" : "OpenRouter is drafting…"}</p>}
      {draft && <section className="panel">
        <h3>{locale === "ru" ? "Предложение OpenRouter" : "OpenRouter suggestion"}</h3>
        {draftMode === "spec" && <><strong>{draft.title}</strong><div className="markdown"><ReactMarkdown>{draft.description}</ReactMarkdown></div><div className="markdown"><ReactMarkdown>{draft.agent_instructions}</ReactMarkdown></div></>}
        <div className="markdown"><ReactMarkdown>{draft.acceptance_criteria}</ReactMarkdown></div>
        <button className="btn btn-primary" type="button" disabled={busy} onClick={() => { if (draftMode === "spec") { setTitle(draft.title); setDescription(draft.description); setInstructions(draft.agent_instructions); } setCriteria(draft.acceptance_criteria); setDraft(null); }}>{locale === "ru" ? "Применить к форме" : "Apply to form"}</button>
        <button className="btn" type="button" onClick={() => setDraft(null)}>{locale === "ru" ? "Отклонить" : "Dismiss"}</button>
      </section>}
      {(/!\[[^\]]*\]\(/.test(description)) && <div className="description-preview markdown" aria-label={t("form.preview")}>
        <ReactMarkdown components={{ img: ({ src, alt }) => <img src={screenshots.find(image => image.marker === src)?.preview ?? src} alt={alt} /> }}>{description}</ReactMarkdown>
      </div>}
      <label>{t("form.criteria")}<textarea aria-label={t("form.criteria")} className="input" rows={3} value={criteria} onChange={e => setCriteria(e.target.value)} placeholder={t("form.criteriaPlaceholder")} /></label>
      {projectInstructions && <details><summary>{t("instructions.inherited")}</summary><div className="markdown"><ReactMarkdown>{projectInstructions}</ReactMarkdown></div></details>}
      <label>{t("instructions.task")}<textarea aria-label={t("instructions.task")} className="input" rows={5} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder={t("instructions.taskHint")} /></label>
      <small className="muted">{t("instructions.hint")}</small>
      <div className="form-grid"><label>{t("newTask.tagsLabel")}<input className="input" value={tags} onChange={e => setTags(e.target.value)} /></label><label>{t("newTask.assignLabel")}<select className="input" value={assigned} onChange={e => setAssigned(e.target.value)}><option value="">{t("newTask.assignAnyone")}</option>{[...new Set([...agents, ...(assigned ? [assigned] : [])])].map(a => <option key={a}>{a}</option>)}</select></label></div>
      <details><summary>{t("card.repo")}</summary><label>{t("newTask.repoLabel")}<input className="input mono" value={repo} onChange={e => setRepo(e.target.value)} /></label><label>{t("newTask.baseLabel")}<input className="input mono" value={branch} onChange={e => setBranch(e.target.value)} /></label></details>
      <label className="file-picker">{t("form.files")}<span className="btn">{t("form.upload")}</span><input type="file" multiple disabled={busy} onChange={e => { setFiles(previous => [...previous, ...Array.from(e.target.files ?? [])]); e.target.value = ""; }} /><small className="muted">{t("form.fileHint")}</small></label>
      {files.map((f, i) => <small className="muted" key={i}>{f.name}<br /></small>)}
      {error && <p role="alert" className="error-banner">{error}</p>}
      <div className="form-actions"><button className="btn" type="button" disabled={busy} onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-primary" disabled={busy || generating || !title.trim()}>{busy ? t("newTask.creating") : task || savedId ? t("form.save") : t("newTask.create")}</button></div>
    </form>
  </div>;
}
