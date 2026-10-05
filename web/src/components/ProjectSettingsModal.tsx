import { useState } from "react";
import { api } from "../api";
import { useT } from "../i18n.tsx";
import { projectTemplate } from "../agentTemplates";
import type { Project } from "../types";

export function ProjectSettingsModal({ project, onClose, onSaved }: { project: Project; onClose: () => void; onSaved: (p: Project) => void }) {
  const { t, locale } = useT();
  const [name, setName] = useState(project.name);
  const [repo, setRepo] = useState(project.repo_path ?? "");
  const [branch, setBranch] = useState(project.default_branch ?? "");
  const [instructions, setInstructions] = useState(project.agent_instructions);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function appendTemplate(odyssey = false) {
    setInstructions(previous => [previous, projectTemplate(repo, locale, odyssey)].filter(Boolean).join("\n\n"));
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const saved = await api.updateProject(project.id, { name: name.trim(), repo_path: repo.trim() || null, default_branch: branch.trim() || null, agent_instructions: instructions });
      onSaved(saved); onClose();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onClick={() => !busy && onClose()}><form className="card modal task-modal" role="dialog" aria-modal="true" aria-labelledby="project-settings-title" onClick={e => e.stopPropagation()} onSubmit={submit}>
    <h2 id="project-settings-title">{t("instructions.settings")}</h2>
    <label>{t("projects.name")}<input className="input" required value={name} onChange={e => setName(e.target.value)} /></label>
    <label>{t("projects.repo")}<input className="input mono" value={repo} onChange={e => setRepo(e.target.value)} /></label>
    <label>{t("projects.branch")}<input className="input mono" value={branch} onChange={e => setBranch(e.target.value)} /></label>
    <label>{t("instructions.project")}<textarea aria-label={t("instructions.project")} className="input" rows={12} value={instructions} onChange={e => setInstructions(e.target.value)} /></label>
    <p className="muted">{t("instructions.projectHint")}</p>
    <div className="form-actions"><button className="btn" type="button" disabled={busy} onClick={() => appendTemplate()}>{t("instructions.template")}</button><button className="btn" type="button" disabled={busy} onClick={() => appendTemplate(true)}>{t("instructions.odyssey")}</button></div>
    <small className="muted">{t("instructions.templateHint")}</small>
    {error && <p role="alert" className="error-banner">{error}</p>}
    <div className="form-actions"><button className="btn" type="button" disabled={busy} onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-primary" disabled={busy || !name.trim()}>{t("form.save")}</button></div>
  </form></div>;
}
