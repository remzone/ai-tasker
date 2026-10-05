import { useEffect, useState } from "react";
import { api, subscribeWebSocket } from "../api";
import type { WSSubscription } from "../api";
import type { Task, TaskStatus, Project } from "../types";
import { WorkflowPanel } from "../components/WorkflowPanel";
import { ProjectSettingsModal } from "../components/ProjectSettingsModal";
import { Column } from "../components/Column";
import { NewTaskModal } from "../components/NewTaskModal";
import { useT } from "../i18n.tsx";

const COLUMNS: TaskStatus[] = ["todo", "ready", "in_progress", "review", "acceptance", "done"];

export function Board({ project, onOpenTask, onProjectUpdated }: { project: Project; onProjectUpdated: (p: Project) => void; onOpenTask: (id: number) => void }) {
  const { t } = useT();
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [lastProgress, setLastProgress] = useState<Record<number, string>>({});
  const [workflowTask, setWorkflowTask] = useState<Task | null>(null);
  const [settings, setSettings] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [, setTick] = useState(0);

  async function refresh() {
    const [tasks, lp] = await Promise.all([
      api.listTasks(undefined, project.id),
      api.listLastProgressTimestamps(),
    ]);
    setTasks(tasks);
    setLastProgress(lp);
  }

  useEffect(() => {
    let sub: WSSubscription | null = null;
    let cancelled = false;
    refresh().catch(e => setError(String(e)));
    subscribeWebSocket(null, () => { refresh().catch(e => setError(String(e))); }).then((s) => {
      if (cancelled) {
        s.close();
      } else {
        sub = s;
      }
    });
    return () => {
      cancelled = true;
      sub?.close();
    };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(id);
  }, []);

  async function handleDrop(taskId: number, status: TaskStatus) {
    const task = tasks.find(entry => entry.id === taskId);
    if (!task || task.status === status) return;
    setError("");
    if ((status === "review" || status === "done" || (status === "in_progress" && ["review", "acceptance"].includes(task.status))) && ["in_progress", "review", "acceptance"].includes(task.status)) {
      setWorkflowTask(task); return;
    }
    try {
      const updated = status === "ready" ? await api.workflow(taskId, "ready")
        : status === "in_progress" && task.status === "ready" ? await api.workflow(taskId, "start")
        : status === "acceptance" && ["in_progress", "review"].includes(task.status) ? await api.workflow(taskId, "human_review")
        : await api.updateTask(taskId, { status });
      setTasks(previous => previous.map(entry => entry.id === taskId ? updated : entry));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await refresh();
    }
  }

  return (
    <div style={{ padding: "20px 20px 24px", display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
          gap: 12,
        }}
      >
        <div>
          <div className="eyebrow" style={{ marginBottom: 2 }}>{t("board.eyebrow")}</div>
          <h2 style={{ margin: 0 }}>{project.name}</h2><p className="muted" style={{ margin: "4px 0" }}>{t("board.subtitle")}</p>
        </div>
        <div className="form-actions"><button className="btn" onClick={() => setSettings(true)}>{t("instructions.settings")}</button><button className="btn btn-primary" onClick={() => setShowNew(true)}>
          {t("board.newTask")}
        </button></div>
      </div>
      {error && <p role="alert" className="error-banner">{error}</p>}
      <div className="board-toolbar"><strong>{t("board.kanban")}</strong><input className="input" aria-label={t("board.search")} placeholder={t("board.search")} value={search} onChange={e => setSearch(e.target.value)} /></div>
      <div
        style={{
          display: "flex",
          gap: 12,
          overflowX: "auto",
          paddingBottom: 4,
          flex: 1,
          minHeight: "calc(100vh - 360px)",
        }}
      >
        {COLUMNS.map((status) => (
          <Column
            key={status}
            status={status}
            tasks={tasks.filter((t) => t.status === status && `${t.title} ${t.tags.join(" ")}`.toLowerCase().includes(search.toLowerCase()))}
            lastProgress={lastProgress}
            onDrop={handleDrop}
            onOpen={onOpenTask}
          />
        ))}
      </div>
      {workflowTask && <div className="modal-backdrop" onClick={() => setWorkflowTask(null)}><div className="card modal" role="dialog" aria-modal="true" aria-label={t("workflow.title")} onClick={event => event.stopPropagation()}><div className="modal-heading"><h2>{workflowTask.title}</h2><button className="btn btn-ghost" aria-label={t("common.close")} onClick={() => setWorkflowTask(null)}>×</button></div><WorkflowPanel task={workflowTask} onChanged={async () => { await refresh(); setWorkflowTask(null); }} /></div></div>}
      {settings && <ProjectSettingsModal project={project} onClose={() => setSettings(false)} onSaved={onProjectUpdated} />}
      {showNew && <NewTaskModal project={project} onClose={() => setShowNew(false)} onCreated={() => refresh()} />}
      <p className="muted" style={{ marginTop: 16 }}>{t("board.tipNew")}</p>
      {tasks.some(tk => tk.status === "blocked" || tk.status === "cancelled") && <details><summary>{t("board.legacy")}</summary>{tasks.filter(tk => tk.status === "blocked" || tk.status === "cancelled").map(tk => <button className="btn" key={tk.id} onClick={() => onOpenTask(tk.id)}>#{tk.id} {tk.title}</button>)}</details>}
    </div>
  );
}
