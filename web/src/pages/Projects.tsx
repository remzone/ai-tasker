import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project, Task } from "../types";
import { useT } from "../i18n.tsx";

export function Projects({ projects, onOpen, onCreated }: { projects: Project[]; onOpen: (p: Project) => void; onCreated: (p: Project) => void }) {
  const { t } = useT();
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [repo, setRepo] = useState("");
  const [instructions, setInstructions] = useState("");
  const [branch, setBranch] = useState("main");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  useEffect(() => { api.listTasks().then(setTasks).catch(e => setError(String(e))); }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try { const p = await api.createProject({ name: name.trim(), repo_path: repo.trim(), default_branch: branch.trim() || undefined, agent_instructions: instructions }); onCreated(p); setShowNew(false); }
    catch(e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <div className="page">
    <div className="page-heading"><div><div className="eyebrow">AI Tasker</div><h1>{t("projects.title")}</h1><p className="muted">{t("projects.subtitle")}</p></div><button className="btn btn-primary" onClick={() => setShowNew(true)}>＋ {t("projects.new")}</button></div>
    {error && <p role="alert" className="error-banner">{error}</p>}
    {projects.length === 0 && <div className="empty-state"><span className="empty-icon">▦</span><h3>{t("projects.empty")}</h3><button className="btn btn-primary" onClick={() => setShowNew(true)}>{t("projects.new")}</button></div>}
    <div className="project-grid">{projects.map(p => { const pt = tasks.filter(tk => tk.project_id === p.id); const done = pt.filter(tk => tk.status === "done").length; return <button className="project-card" key={p.id} onClick={() => onOpen(p)}><div className="project-card-head"><span className="project-icon">▦</span><span className="badge badge-neutral">{t("projects.tasks", { count: pt.length })}</span></div><h3>{p.name}</h3><p className="mono muted repo-path">{p.repo_path || "—"}</p><div className="project-progress"><span style={{ width: `${pt.length ? done / pt.length * 100 : 0}%` }} /></div><div className="project-card-footer"><span className="muted">{done} / {pt.length}</span><span>{t("projects.open")}</span></div></button>; })}</div>
    {showNew && <div className="modal-backdrop" onClick={() => !busy && setShowNew(false)}><form className="card modal" role="dialog" aria-modal="true" aria-labelledby="project-title" onClick={e => e.stopPropagation()} onSubmit={submit}><h2 id="project-title">{t("projects.new")}</h2><label>{t("projects.name")}<input className="input" autoFocus required value={name} onChange={e => setName(e.target.value)} /></label><label>{t("projects.repo")}<input className="input mono" required placeholder="/home/user/projects/my-project" value={repo} onChange={e => setRepo(e.target.value)} /></label><label>{t("projects.branch")}<input className="input mono" value={branch} onChange={e => setBranch(e.target.value)} /></label><label>{t("instructions.project")}<textarea aria-label={t("instructions.project")} className="input" rows={6} value={instructions} onChange={e => setInstructions(e.target.value)} /></label><small className="muted">{t("instructions.projectHint")}</small>{error && <p role="alert" className="error-banner">{error}</p>}<div className="form-actions"><button type="button" className="btn" disabled={busy} onClick={() => setShowNew(false)}>{t("common.cancel")}</button><button className="btn btn-primary" disabled={busy || !name.trim() || !repo.trim()}>{t("projects.create")}</button></div></form></div>}
  </div>;
}
