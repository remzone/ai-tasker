import { useEffect, useState } from "react";
import { api } from "./api";
import { Login } from "./pages/Login";
import { Admin } from "./pages/Admin";
import { Board } from "./pages/Board";
import { CardDetail } from "./pages/CardDetail";
import { Projects } from "./pages/Projects";
import { getStoredTheme, setTheme, toggleTheme, type Theme } from "./theme";
import { LANGS, useT } from "./i18n.tsx";
import type { Project } from "./types";

type View = "loading" | "login" | "projects" | "board" | "admin" | "card";

export default function App() {
  const { t, locale, setLocale } = useT();
  const [view, setView] = useState<View>("loading");
  const [me, setMe] = useState<{ is_admin: boolean } | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [taskId, setTaskId] = useState(0);
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme() ?? "dark");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [error, setError] = useState("");

  async function loadProjects() { setProjects(await api.listProjects()); }
  async function recheck() {
    try {
      setMe(await api.me());
      await loadProjects();
      setView("projects");
    } catch { setMe(null); setView("login"); }
  }
  useEffect(() => {
    const stored = getStoredTheme();
    if (stored) setTheme(stored);
    void recheck();
    const unauthorized = () => { setMe(null); setView("login"); };
    window.addEventListener("kanban:unauthorized", unauthorized);
    return () => window.removeEventListener("kanban:unauthorized", unauthorized);
  }, []);
  function navigate(next: View) { setView(next); setMobileOpen(false); }
  function openProject(p: Project) { setProject(p); navigate("board"); }
  if (view === "loading") return <div className="loading">{t("common.loading")}</div>;
  if (view === "login") return <Login onLoggedIn={recheck} />;
  return <div className="app-shell">
    {mobileOpen && <button className="sidebar-overlay" aria-label={t("common.close")} onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar ${mobileOpen ? "is-open" : ""}`}>
      <button className="brand" onClick={() => navigate("projects")}><span className="brand-mark">AI</span><span>AI Tasker<small>{t("nav.workspace")}</small></span></button>
      <nav aria-label={t("nav.workspace")}>
        <button className={`nav-link ${view === "projects" ? "active" : ""}`} onClick={() => navigate("projects")}><span aria-hidden>▦</span>{t("nav.projects")}</button>
        <div className="sidebar-label">{t("nav.projects")}</div>
        {projects.map(p => <button key={p.id} className={`nav-link project-link ${project?.id === p.id && (view === "board" || view === "card") ? "active" : ""}`} onClick={() => openProject(p)}><span className="project-dot" aria-hidden /><span className="ellipsis">{p.name}</span></button>)}
        {me?.is_admin && <button className={`nav-link ${view === "admin" ? "active" : ""}`} onClick={() => navigate("admin")}><span aria-hidden>⚙</span>{t("nav.settings")}</button>}
      </nav>
      <div className="sidebar-footer"><span className="badge badge-info">MCP</span><p className="muted">{t("board.subtitle")}</p><button className="btn btn-ghost" onClick={async () => { try { await api.logout(); setView("login"); } catch (e) { setError(String(e)); } }}>{t("nav.logout")}</button></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <button className="btn btn-ghost mobile-menu" aria-label={t("nav.workspace")} onClick={() => setMobileOpen(v => !v)}>☰</button>
        <div className="breadcrumbs"><button onClick={() => navigate("projects")}>{t("nav.projects")}</button>{(view === "board" || view === "card") && project && <><span>/</span><button onClick={() => navigate("board")}>{project.name}</button><span>/</span><span>{view === "card" ? `#${taskId}` : "Kanban"}</span></>}</div>
        <div className="topbar-actions"><button className="btn btn-ghost btn-sm" onClick={() => setThemeState(toggleTheme())} aria-label={t("nav.theme.toggle")}>{theme === "dark" ? "☀" : "☾"}</button><div className="language-toggle">{LANGS.map(l => <button key={l.code} className={locale === l.code ? "selected" : ""} onClick={() => setLocale(l.code)}>{l.label}</button>)}</div><span className="avatar">U</span></div>
      </header>
      {error && <p role="alert" className="error-banner">{error}</p>}
      <main>
        {view === "projects" && <Projects projects={projects} onOpen={openProject} onCreated={async p => { await loadProjects(); openProject(p); }} />}
        {view === "board" && project && <Board key={project.id} project={project} onProjectUpdated={p => { setProject(p); setProjects(previous => previous.map(entry => entry.id === p.id ? p : entry)); }} onOpenTask={id => { setTaskId(id); navigate("card"); }} />}
        {view === "card" && <CardDetail key={taskId} taskId={taskId} onBack={() => navigate("board")} />}
        {view === "admin" && <Admin onBack={() => navigate("projects")} />}
      </main>
    </div>
  </div>;
}
