import { useEffect, useState } from "react";
import { api } from "../api";
import type { Task } from "../types";
import { useT } from "../i18n.tsx";

export function WorkflowPanel({ task, onChanged }: { task: Task; onChanged: () => void | Promise<void> }) {
  const { t } = useT();
  const [reviewer, setReviewer] = useState(task.review_assigned_to ?? "");
  const [summary, setSummary] = useState(task.work_summary);
  const [comment, setComment] = useState("");
  const [agents, setAgents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.listTokens().then(tokens => setAgents([...new Set(tokens.map(token => token.agent_name))])).catch(() => {}); }, []);
  async function decide(action: "review" | "human_review" | "accept" | "return") {
    setBusy(true); setError("");
    try {
      await api.workflow(task.id, action, action === "review" ? summary.trim() : comment.trim(), action === "review" ? reviewer.trim() || undefined : undefined);
      await onChanged();
      setComment("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="panel workflow-panel">
    <h3>{t("workflow.title")}</h3>
    <p className="muted">{t("workflow.hint")}</p>
    {task.review_assigned_to && <p className="muted">{t("workflow.assignedReview", { name: task.review_assigned_to })}</p>}
    {task.reviewer && <p className="muted">{t("card.reviewer", { name: task.reviewer })}</p>}
    <label>{t("workflow.summary")}<textarea className="input" aria-label={t("workflow.summary")} rows={3} disabled={busy} value={summary} onChange={e => setSummary(e.target.value)} /></label>
    <label>{t("workflow.agent")}<input className="input" aria-label={t("workflow.agent")} list={`review-agents-${task.id}`} placeholder={t("workflow.anyAgent")} disabled={busy} value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
    <datalist id={`review-agents-${task.id}`}>{agents.map(agent => <option value={agent} key={agent} />)}</datalist>
    <button className="btn" disabled={busy || !summary.trim()} onClick={() => decide("review")}>{t("workflow.sendAgent")}</button>
    <label style={{ marginTop: 14 }}>{t("workflow.comment")}<textarea className="input" aria-label={t("workflow.comment")} rows={3} disabled={busy} value={comment} onChange={e => setComment(e.target.value)} /></label>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {task.status !== "acceptance" && <button className="btn" disabled={busy} onClick={() => decide("human_review")}>{t("workflow.sendHuman")}</button>}
      <button className="btn btn-primary" disabled={busy} onClick={() => decide("accept")}>{t("workflow.accept")}</button>
      {(task.status === "review" || task.status === "acceptance") && <button className="btn" disabled={busy || !comment.trim()} onClick={() => decide("return")}>{t("card.return")}</button>}
    </div>
    {error && <p role="alert" className="error-banner">{error}</p>}
  </section>;
}
