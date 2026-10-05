import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, subscribeWebSocket } from "../api";
import type { WSSubscription } from "../api";
import type { Attachment, Comment, ProgressEvent, Task, TaskContext } from "../types";
import { ProgressFeed } from "../components/ProgressFeed";
import { CommentList } from "../components/CommentList";
import { ArtifactCard } from "../components/ArtifactCard";
import { WorkflowPanel } from "../components/WorkflowPanel";
import { NewTaskModal } from "../components/NewTaskModal";
import { STATUS_META } from "../statusMeta";
import { useT, localeBcp47 } from "../i18n.tsx";

export function CardDetail({ taskId, onBack }: { taskId: number; onBack: () => void }) {
  const { t, locale } = useT();
  const [task, setTask] = useState<Task | null>(null);
  const [context, setContext] = useState<TaskContext | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    const [tk, pr, cm, at] = await Promise.all([api.getTaskContext(taskId), api.listProgress(taskId), api.listComments(taskId), api.listAttachments(taskId)]);
    setTask(tk); setContext(tk); setProgress(pr); setComments(cm); setAttachments(at);
  }
  useEffect(() => {
    let sub: WSSubscription | null = null; let cancelled = false;
    const update = () => { refresh().catch(e => setError(String(e))); };
    update();
    subscribeWebSocket(taskId, update).then(s => { if (cancelled) s.close(); else sub = s; });
    return () => { cancelled = true; sub?.close(); };
  }, [taskId]);
  async function action(work: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await work(); await refresh(); }
    catch(e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  if (!task) return <div className="loading">{error ? <p role="alert">{error}</p> : t("common.loading")}</div>;
  const meta = STATUS_META[task.status];
  const history = progress.filter(e => e.payload.decision);
  return <div className="page task-page">
    <button className="btn btn-ghost btn-sm" onClick={onBack}>{t("card.back")}</button>
    <div className="page-heading"><div><div className="eyebrow">{t("card.taskPrefix", { id: task.id })}</div><h1>{task.title}</h1><span className={`badge badge-${meta.badge}`}><span className="badge-dot" />{t(meta.labelKey)}</span></div><button className="btn" onClick={() => setEditing(true)}>{t("common.edit")}</button></div>
    {error && <p role="alert" className="error-banner">{error}</p>}
    <div className="task-layout">
      <div className="task-main">
        <section className="panel"><h3>{t("card.section.details")}</h3><div className="markdown"><ReactMarkdown>{task.description || t("card.noDescription")}</ReactMarkdown></div><h3>{t("form.criteria")}</h3><div className="markdown"><ReactMarkdown>{task.acceptance_criteria || t("card.noCriteria")}</ReactMarkdown></div></section>
        <section className="panel"><h3>{t("instructions.title")}</h3><h4>{t("instructions.project")}</h4><div className="markdown"><ReactMarkdown>{context?.project_agent_instructions || t("instructions.empty")}</ReactMarkdown></div><h4>{t("instructions.task")}</h4><div className="markdown"><ReactMarkdown>{task.agent_instructions || t("instructions.empty")}</ReactMarkdown></div><p className="muted">{t("instructions.hint")}</p><button className="btn" onClick={() => { setCopied(false); void action(async () => { const current = await api.getTaskContext(taskId); setPrompt(current.agent_prompt); }); }}>{t("instructions.prompt")}</button></section>
        <section className="panel"><h3>{t("card.summary")}</h3><div className="markdown"><ReactMarkdown>{task.work_summary || t("card.noSummary")}</ReactMarkdown></div></section>
        <section className="panel"><h3>{t("card.history")}</h3>{!history.length && <p className="muted">{t("card.historyEmpty")}</p>}{history.map(ev => { const st = ev.payload.status as { from: keyof typeof STATUS_META; to: keyof typeof STATUS_META }; return <div className="decision-entry" key={ev.id}><div><span className={`badge badge-${ev.payload.decision === "APPROVE" || ev.payload.decision === "ACCEPT" ? "success" : "warning"}`}>{String(ev.payload.decision)}</span><small className="muted">{ev.agent} · {new Date(ev.created_at).toLocaleString(localeBcp47(locale))}</small></div><p className="muted">{t(STATUS_META[st.from].labelKey)} → {t(STATUS_META[st.to].labelKey)}</p><ReactMarkdown>{String(ev.payload.content ?? "")}</ReactMarkdown></div>; })}</section>
        <section className="panel"><h3>{t("card.section.progress")}</h3>{!progress.length && <p className="muted">{t("card.noProgress")}</p>}<ProgressFeed events={progress} /><CommentList taskId={taskId} comments={comments} taskStatus={task.status} onPosted={refresh} /></section>
      </div>
      <aside className="task-aside">
        {["in_progress", "review", "acceptance"].includes(task.status) && <WorkflowPanel key={`${task.id}-${task.status}-${task.review_assigned_to ?? ""}`} task={task} onChanged={refresh} />}
        <section className="panel"><h3>{t("card.repo")}</h3><p className="mono repo-path">{task.repo_path || "—"}</p>{task.base_branch && <p className="muted mono">{task.base_branch}{task.branch ? ` → ${task.branch}` : ""}</p>}{task.pr_url && <a href={task.pr_url} target="_blank" rel="noreferrer">PR ↗</a>}<hr /><p className="muted">{task.claimed_by ? t("task.claimedBy", { name: task.claimed_by }) : task.status === "in_progress" ? t("card.returnWaiting") : t("newTask.assignAnyone")}</p>{task.assigned_to && <span className="badge badge-info">→ {task.assigned_to}</span>}{task.reviewer && <p className="muted">{t("card.reviewer", { name: task.reviewer })}</p>}{task.status === "review" && <p className="muted">{t("card.waitReview")}</p>}<div className="tags">{task.tags.map(tag => <span className="tag" key={tag}>{tag}</span>)}</div>{["todo", "in_progress", "review", "acceptance"].includes(task.status) && <button className="btn btn-primary" disabled={busy} onClick={() => action(() => api.workflow(taskId, "ready"))}>{t("card.moveReady")}</button>}{["ready", "review"].includes(task.status) && <button className="btn btn-primary" disabled={busy || (task.status === "review" ? !!task.reviewer : !!task.claimed_by)} onClick={() => action(() => api.runAgent(taskId))}>{t(task.status === "review" ? "agent.review" : "agent.run")}</button>}{task.status === "ready" && <button className="btn" disabled={busy} onClick={() => action(() => api.updateTask(taskId, { status: "todo" }))}>{t("card.moveBacklog")}</button>}{(task.status === "blocked" || task.status === "cancelled" || task.status === "done") && <button className="btn" disabled={busy} onClick={() => action(() => api.updateTask(taskId, { status: task.status === "blocked" ? "ready" : "todo" }))}>{t("card.reopenReady")}</button>}</section>
        <section className="panel"><h3>{t("form.files")}</h3><div className="attachments">{attachments.map(a => <ArtifactCard key={a.id} artifact={a} description={a.description || undefined} />)}</div><label className="upload-label"><span className="btn">{t("form.upload")}</span><input type="file" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void action(() => api.uploadAttachment(taskId, file)); e.target.value = ""; }} /><small className="muted">{t("form.fileHint")}</small></label></section>
      </aside>
    </div>
    {prompt !== null && <div className="modal-backdrop" onClick={() => setPrompt(null)}><div className="card modal task-modal" role="dialog" aria-modal="true" aria-labelledby="agent-prompt-title" onClick={e => e.stopPropagation()}><h2 id="agent-prompt-title">{t("instructions.prompt")}</h2><textarea className="input mono" rows={18} readOnly aria-label={t("instructions.prompt")} value={prompt} onFocus={e => e.currentTarget.select()} /><p className="muted">{t("instructions.copyHint")}</p><div className="form-actions"><button className="btn" onClick={() => setPrompt(null)}>{t("common.close")}</button><button className="btn btn-primary" onClick={async () => { try { await navigator.clipboard.writeText(prompt); setCopied(true); } catch { setCopied(false); } }}>{copied ? t("instructions.copied") : t("instructions.copy")}</button></div></div></div>}
    {editing && <NewTaskModal task={task} onClose={() => setEditing(false)} onCreated={() => { void refresh(); }} />}
  </div>;
}
