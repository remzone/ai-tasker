export type TaskStatus =
  | "todo"
  | "ready"
  | "in_progress"
  | "review"
  | "acceptance"
  | "done"
  | "blocked"
  | "cancelled";

export interface Task {
  id: number;
  project_id: number | null;
  title: string;
  description: string;
  agent_instructions: string;
  acceptance_criteria: string;
  work_summary: string;
  reviewer: string | null;
  review_assigned_to: string | null;
  status: TaskStatus;
  tags: string[];
  claimed_by: string | null;
  claimed_at: string | null;
  assigned_to: string | null;
  sort_order: number;
  branch: string | null;
  pr_url: string | null;
  pr_status: string | null;
  repo_path: string | null;
  base_branch: string | null;
  created_at: string;
  updated_at: string;
}

export type ProgressKind =
  | "text"
  | "diff"
  | "artifact_ref"
  | "error"
  | "status_change";

export interface ProgressEvent {
  id: number;
  task_id: number;
  agent: string;
  kind: ProgressKind;
  payload: { content?: string; [k: string]: unknown };
  created_at: string;
}

export interface ArtifactMeta {
  id?: number;
  path: string;
  kind: string; // "screenshot" | "log" | "diff.patch" | "file" | ...
}

export interface Comment {
  id: number;
  task_id: number;
  author: string;
  content: string;
  seen_by_agent: boolean;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  agent_instructions: string;
  repo_path: string | null;
  default_branch: string | null;
  created_at: string;
}
export interface Attachment {
  id: number;
  task_id: number;
  path: string;
  kind: string;
  description: string | null;
}

export interface TaskContext extends Task {
  project_agent_instructions: string;
  effective_agent_instructions: string;
  agent_prompt: string;
}
