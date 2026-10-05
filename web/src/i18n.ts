/**
 * Tiny i18n engine — no external deps.
 *
 * Two locales (ru/en), flat dot-namespace keys, `{param}` interpolation,
 * and a Russian-plural helper for the one plural case in the UI (diff hunks).
 * A subscribe/store layer in i18n.tsx wires this into React.
 */

export type Locale = "ru" | "en";

export const LANGS: { code: Locale; label: string }[] = [
  { code: "ru", label: "RU" },
  { code: "en", label: "EN" },
];

// ── Message catalogs ────────────────────────────────────────────────────────
// Keys are flat dotted strings grouped by feature. English is the source
// catalog; Russian mirrors it 1:1. If a key is missing in the active locale
// we fall back to English, then to the key itself (so a missing translation
// is visible, not invisible).

type Catalog = Record<string, string>;

const en: Catalog = {
  "instructions.settings": "Project settings",
  "instructions.project": "Project restrictions and agent instructions",
  "instructions.projectHint": "Apply to all project tasks and reviews. Updates are included when an agent reads task context.",
  "instructions.task": "Additional task restrictions and agent instructions",
  "instructions.taskHint": "File scope, compatibility, API/UX requirements, runtime actions and verification commands",
  "instructions.inherited": "Inherited project restrictions",
  "instructions.title": "Agent instructions",
  "instructions.hint": "Included in MCP context for execution and review. Filesystem permissions are configured in the agent environment.",
  "instructions.empty": "Not specified",
  "instructions.template": "Add restrictions template",
  "instructions.odyssey": "Add Odyssey template",
  "instructions.templateHint": "Templates are appended; existing text is preserved. Replace bracketed placeholders before saving.",
  "instructions.taskTemplate": "Add task template",
  "instructions.prompt": "Full agent prompt",
  "instructions.copyHint": "Copy this prompt into an agent conversation. You can also select all text and use Ctrl+C.",
  "instructions.copy": "Copy prompt",
  "instructions.copied": "Copied",
  "workflow.title": "Review result",
  "workflow.hint": "Send the result to an agent for review or verify and accept it yourself.",
  "agent.run": "Run Codex",
  "agent.review": "Run Codex review",
  "agent.launching": "Starting…",
  "agent.running": "Agent running",
  "workflow.summary": "Work summary for review",
  "workflow.agent": "Review agent",
  "workflow.anyAgent": "Any available agent",
  "workflow.sendAgent": "Send to review agent",
  "workflow.sendHuman": "Send to human review",
  "workflow.accept": "Verified — accept as human",
  "workflow.comment": "Comment or requested changes",
  "workflow.assignedReview": "Review assigned: {name}",
  "workflow.start": "Start work",
  "admin.mcpTitle": "Connect Codex",
  "admin.mcpSteps": "Create or select an agent token below, then copy the Codex config. Tokens can be shown and copied again.",
  "admin.replaceConfirm": "Generate a replacement? The old token will stop working. Update the agent configuration afterwards.",
  "admin.copyError": "Clipboard unavailable. Show the token and copy it manually.",
  "admin.checkSuccess": "MCP works: list_projects and list_tasks accepted this token.",
  "admin.checkFailed": "MCP connection failed.",
  "admin.checking": "Checking…",
  "admin.checkMcp": "Check MCP",
  "admin.closeToken": "Close",
  "admin.tokenFor": "Token for",
  "admin.agentToken": "Agent token",
  "admin.hideToken": "Hide",
  "admin.showToken": "Show",
  "admin.copyToken": "Copy token",
  "admin.copyHeader": "Copy Authorization",
  "admin.copyConfig": "Copy Codex config",
  "admin.openToken": "Show / copy",
  "admin.replaceToken": "Replace",
  "admin.generateToken": "Generate token",
  "admin.configHint": "Replace the existing tasker block with the copied config. In the MCP settings, leave Bearer token env var empty and use the copied Authorization value. Restart Codex and open a new chat.",
  "admin.agentArgument": "For mutation tools, use agent =",
  "admin.mcpHint": "Create a token below. The agent argument must match the token name.",
  "admin.mcpEnv": "Set AI_TASKER_MCP_TOKEN in the VS Code/Codex environment.",

  "nav.projects": "Projects",
  "nav.workspace": "Workspace",
  "nav.settings": "Settings & MCP",
  "projects.title": "My projects",
  "projects.subtitle": "From idea to accepted work, with your AI.",
  "projects.new": "New project",
  "projects.name": "Project name",
  "projects.repo": "Repository path",
  "projects.branch": "Default branch",
  "projects.empty": "Create your first project and add tasks.",
  "projects.open": "Open Kanban →",
  "projects.create": "Create project",
  "projects.tasks": "Tasks: {count}",
  "board.search": "Find a task…",
  "board.kanban": "Kanban",
  "board.subtitle": "Plan work. Follow AI. Accept the result.",
  "board.tipNew": "Move a task to Ready for an agent to claim it. Review and acceptance require explicit decisions.",
  "board.legacy": "Other states",
  "form.criteria": "Acceptance criteria",
  "form.criteriaPlaceholder": "What must be delivered and how should it be checked?",
  "form.save": "Save",
  "form.editTask": "Edit task",
  "form.files": "Files & screenshots",
  "form.upload": "Attach file",
  "form.pasteHint": "Paste a screenshot with Ctrl+V (⌘V on Mac). It will be attached when you save.",
  "form.pasteTooLarge": "The screenshot exceeds 20 MB.",
  "form.screenshot": "Screenshot",
  "form.preview": "Description preview",
  "form.fileHint": "Up to 20 MB per file",
  "form.partial": "Task created, but an attachment failed. Open the task and retry.",
  "card.summary": "Work summary",
  "card.history": "AI review & return history",
  "card.historyEmpty": "No decisions yet.",
  "card.repo": "Repository",
  "card.reviewer": "Reviewer: {name}",
  "card.noCriteria": "No criteria yet.",
  "card.noSummary": "The agent has not submitted a result yet.",
  "card.noProgress": "Agent activity will appear here after a claim.",
  "card.acceptTitle": "Your acceptance",
  "card.acceptHint": "AI review passed. Check the result and make your decision.",
  "card.accept": "Accept work",
  "card.return": "Return for changes",
  "card.returnComment": "Decision comment (required for returns)",
  "card.waitReview": "Awaiting AI review via MCP.",
  "card.moveReady": "Make available to AI",
  "card.moveBacklog": "Move to backlog",
  "card.returnWaiting": "Awaiting claim after return",

  // common
  "common.loading": "Loading…",
  "common.backToBoard": "← Back to board",
  "common.cancel": "Cancel",
  "common.send": "Send",
  "common.add": "Add",
  "common.edit": "Edit",
  "common.close": "Close",
  "common.dismiss": "Dismiss",
  "common.copy": "Copy",
  "common.copied": "Copied",
  "common.never": "never",
  "common.empty": "empty",

  // nav
  "nav.admin": "Admin",
  "nav.logout": "Log out",
  "nav.theme.toLight": "Switch to light",
  "nav.theme.toDark": "Switch to dark",
  "nav.theme.toggle": "Toggle theme",

  // login
  "login.eyebrow.setup": "First run",
  "login.eyebrow.login": "Sign in",
  "login.brand": "AI Tasker",
  "login.subtitle.setup": "Create the admin account to get started.",
  "login.subtitle.login": "Operator console for pull-based agents.",
  "login.usernameLabel": "Username",
  "login.passwordLabel": "Password",
  "login.confirmLabel": "Confirm password",
  "login.usernamePlaceholder": "username",
  "login.error.shortPassword": "Password must be at least 8 characters",
  "login.error.mismatch": "Passwords do not match",
  "login.error.failed": "Login failed",
  "login.button.setup": "Create admin",
  "login.button.login": "Log in",

  // board
  "board.eyebrow": "Board",
  "board.title": "All tasks",
  "board.newTask": "+ New task",
  "board.tip": "Drag cards between columns. Drop into {ready} to make them available to agents via MCP.",
  "board.tipReady": "READY",

  // column
  "column.empty": "empty",

  // status labels
  "status.todo": "Todo",
  "status.ready": "Ready",
  "status.in_progress": "Active",
  "status.review": "Review",
  "status.acceptance": "Acceptance",
  "status.done": "Done",
  "status.blocked": "Blocked",
  "status.cancelled": "Cancelled",

  // task card
  "task.live": "live",
  "task.reservedTooltip": "Reserved for {agent}",
  "task.claimedBy": "claimed by {name}",
  "task.pr": "PR #{num}",
  "task.prFallback": "pr",

  // pr status (server values: merged / closed / null=open)
  "pr.merged": "merged",
  "pr.closed": "closed",
  "pr.open": "open",

  // card detail
  "card.back": "← Back to board",
  "card.taskPrefix": "Task #{id}",
  "card.reservedTooltip": "Reserved for this agent",
  "card.section.progress": "Progress",
  "card.section.details": "Details",
  "card.noDescription": "No description",
  "card.assignedTo": "Assigned to",
  "card.assignAnyone": "Anyone (unassigned)",
  "card.assignTooltip": "Reserve this task for a specific agent. Others won't see or claim it.",
  "card.reopenReady": "Reopen → ready",
  "card.cancel": "Cancel",
  "card.error.assign": "Failed to assign task",
  "card.error.update": "Failed to update task",

  // comments
  "comment.heading": "Comments",
  "comment.empty": "No comments yet.",
  "comment.seen": "seen",
  "comment.pending": "pending",
  "comment.inputPlaceholder": "Add a comment for the agent…",
  "comment.statusAfter": "Status after posting",
  "comment.toInProgress": "→ in_progress",
  "comment.toReady": "→ ready",
  "comment.sending": "Sending…",
  "comment.error": "Failed to post comment",

  // new task modal
  "newTask.eyebrow": "New task",
  "newTask.title": "Create a task",
  "newTask.titleLabel": "Title",
  "newTask.titlePlaceholder": "What needs to be done?",
  "newTask.descLabel": "Description",
  "newTask.descPlaceholder": "Markdown supported",
  "newTask.tagsLabel": "Tags",
  "newTask.tagsPlaceholder": "comma-separated",
  "newTask.repoLabel": "Repo path (optional)",
  "newTask.baseLabel": "Base branch (optional)",
  "newTask.assignLabel": "Assign to (optional)",
  "newTask.assignTooltip": "Reserve this task for a specific agent. Others won't see it.",
  "newTask.assignAnyone": "Anyone (unassigned)",
  "newTask.creating": "Creating…",
  "newTask.create": "Create task",
  "newTask.error": "Failed to create task",

  // progress feed
  "progress.collapseAll": "Collapse all diffs",
  "progress.planning": "Planning transition",
  "progress.expandAll": "Expand all diffs",
  "progress.diff": "diff",
  "progress.hunks": "{count} hunk(s)",

  // admin
  "admin.eyebrow": "Administration",
  "admin.title": "Tokens & users",
  "admin.tokensHeading": "Tokens (agents)",
  "admin.usersHeading": "Users",
  "admin.banner": "Copy now — shown once",
  "admin.agentPlaceholder": "agent_name (e.g. codex)",
  "admin.descPlaceholder": "description (optional)",
  "admin.mint": "Mint",
  "admin.col.agent": "Agent",
  "admin.col.description": "Description",
  "admin.col.created": "Created",
  "admin.col.lastUsed": "Last used",
  "admin.col.role": "Role",
  "admin.col.username": "Username",
  "admin.noTokens": "No tokens yet.",
  "admin.revoke": "Revoke",
  "admin.userPlaceholder": "username",
  "admin.passPlaceholder": "password",
  "admin.admin": "admin",
  "admin.role.admin": "admin",
  "admin.role.user": "user",
  "admin.changePassBody":
    "Change password — enter {your} current admin password and a new password (8+) for {name}.",
  "admin.changePassYour": "your",
  "admin.yourCurrentPass": "your current password",
  "admin.newPassFor": "new password for {name}",
  "admin.changePassword": "Change password",
  "admin.promote": "Promote to admin",
  "admin.demote": "Demote",
  "admin.deleteUser": "Delete user",
  "admin.error.mint": "Failed to mint token",
  "admin.error.revoke": "Failed to revoke token",
  "admin.error.addUser": "Failed to add user",
  "admin.error.removeUser": "Failed to remove user",
  "admin.error.changePass": "Failed to change password",
  "admin.error.adminFlag": "Failed to update admin flag",
};

const ru: Catalog = {
  "instructions.settings": "Настройки проекта",
  "instructions.project": "Общие ограничения и инструкции проекта",
  "instructions.projectHint": "Применяются ко всем задачам проекта и ревью. Изменения попадают в контекст при следующем чтении агентом.",
  "instructions.task": "Дополнительные ограничения и инструкции агента",
  "instructions.taskHint": "Область изменений, совместимость, UX/API, runtime-действия и команды проверок",
  "instructions.inherited": "Ограничения, унаследованные от проекта",
  "instructions.title": "Инструкции для агента",
  "instructions.hint": "Передаются через MCP исполнителю и ревьюеру. Права на файловую систему задаются в окружении агента.",
  "instructions.empty": "Не заданы",
  "instructions.template": "Добавить шаблон ограничений",
  "instructions.odyssey": "Добавить шаблон Odyssey",
  "instructions.templateHint": "Шаблоны добавляются к тексту. Замените поля в квадратных скобках перед сохранением.",
  "instructions.taskTemplate": "Добавить шаблон задачи",
  "instructions.prompt": "Полный промпт для агента",
  "instructions.copyHint": "Скопируйте промпт в диалог с агентом. Также можно выделить весь текст и нажать Ctrl+C.",
  "instructions.copy": "Скопировать промпт",
  "instructions.copied": "Скопировано",
  "workflow.title": "Проверка результата",
  "workflow.hint": "Отправьте результат агенту на ревью или проверьте и примите его сами.",
  "agent.run": "Запустить Codex",
  "agent.review": "Запустить ревью Codex",
  "agent.launching": "Запускаем…",
  "agent.running": "Агент запущен",
  "workflow.summary": "Результат работы для ревью",
  "workflow.agent": "Агент для ревью",
  "workflow.anyAgent": "Любой доступный агент",
  "workflow.sendAgent": "Отправить на ревью агенту",
  "workflow.sendHuman": "Отправить на проверку человеку",
  "workflow.accept": "Проверено — принять человеком",
  "workflow.comment": "Комментарий или замечания",
  "workflow.assignedReview": "Ревью назначено: {name}",
  "workflow.start": "Начать работу",
  "admin.mcpTitle": "Подключение Codex",
  "admin.mcpSteps": "Создайте или выберите токен агента ниже и скопируйте конфиг Codex. Токен можно снова показать и скопировать.",
  "admin.replaceConfirm": "Сгенерировать замену? Старый токен перестанет работать. После этого обновите настройки агента.",
  "admin.copyError": "Буфер обмена недоступен. Покажите токен и скопируйте его вручную.",
  "admin.checkSuccess": "MCP работает: list_projects и list_tasks приняли этот токен.",
  "admin.checkFailed": "Не удалось подключиться к MCP.",
  "admin.checking": "Проверяем…",
  "admin.checkMcp": "Проверить MCP",
  "admin.closeToken": "Закрыть",
  "admin.tokenFor": "Токен агента",
  "admin.agentToken": "Токен агента",
  "admin.hideToken": "Скрыть",
  "admin.showToken": "Показать",
  "admin.copyToken": "Копировать токен",
  "admin.copyHeader": "Копировать Authorization",
  "admin.copyConfig": "Копировать конфиг Codex",
  "admin.openToken": "Показать / копировать",
  "admin.replaceToken": "Заменить",
  "admin.generateToken": "Сгенерировать токен",
  "admin.configHint": "Замените существующий блок tasker скопированным конфигом. В настройках MCP оставьте Bearer token env var пустым и вставьте скопированное значение Authorization. Перезапустите Codex и откройте новый чат.",
  "admin.agentArgument": "В инструментах изменения задачи используйте agent =",
  "admin.mcpHint": "Создайте токен ниже. agent в MCP вызовах должен совпадать с именем токена.",
  "admin.mcpEnv": "Задайте AI_TASKER_MCP_TOKEN в окружении VS Code/Codex.",

  "nav.projects": "Проекты",
  "nav.workspace": "Рабочее пространство",
  "nav.settings": "Настройки и MCP",
  "projects.title": "Мои проекты",
  "projects.subtitle": "От идеи до принятой работы — вместе с вашим AI.",
  "projects.new": "Новый проект",
  "projects.name": "Название проекта",
  "projects.repo": "Путь к репозиторию",
  "projects.branch": "Основная ветка",
  "projects.empty": "Создайте первый проект и добавьте задачи.",
  "projects.open": "Открыть Kanban →",
  "projects.create": "Создать проект",
  "projects.tasks": "Задач: {count}",
  "board.search": "Найти задачу…",
  "board.kanban": "Kanban",
  "board.subtitle": "Планируйте работу. Следите за AI. Принимайте результат.",
  "board.tipNew": "Перенесите задачу в «Готово», чтобы агент мог её взять. Проверка и приёмка выполняются отдельными решениями.",
  "board.legacy": "Другие состояния",
  "form.criteria": "Критерии приёмки",
  "form.criteriaPlaceholder": "Что должно быть выполнено и как это проверить?",
  "form.save": "Сохранить",
  "form.editTask": "Редактировать задачу",
  "form.files": "Файлы и скриншоты",
  "form.upload": "Прикрепить файл",
  "form.pasteHint": "Вставьте скриншот через Ctrl+V (⌘V на Mac). Он прикрепится при сохранении задачи.",
  "form.pasteTooLarge": "Скриншот превышает 20 МБ.",
  "form.screenshot": "Скриншот",
  "form.preview": "Предпросмотр описания",
  "form.fileHint": "До 20 МБ на файл",
  "form.partial": "Задача создана, но файл не загрузился. Откройте задачу и повторите загрузку.",
  "card.summary": "Результат работы",
  "card.history": "AI review и история возвратов",
  "card.historyEmpty": "Решений пока нет.",
  "card.repo": "Репозиторий",
  "card.reviewer": "Проверяет: {name}",
  "card.noCriteria": "Критерии ещё не заданы.",
  "card.noSummary": "Агент ещё не передал результат.",
  "card.noProgress": "Когда агент возьмёт задачу, здесь появится ход работы.",
  "card.acceptTitle": "Ваша приёмка",
  "card.acceptHint": "AI review пройден. Проверьте результат и примите решение.",
  "card.accept": "Принять работу",
  "card.return": "Вернуть на доработку",
  "card.returnComment": "Комментарий к решению (обязателен при возврате)",
  "card.waitReview": "Агент проверяет результат через MCP. Также можно принять работу вручную.",
  "card.moveReady": "Передать агенту",
  "card.moveBacklog": "В бэклог",
  "card.returnWaiting": "Ожидает claim после возврата",

  // common
  "common.loading": "Загрузка…",
  "common.backToBoard": "← К доске",
  "common.cancel": "Отмена",
  "common.send": "Отправить",
  "common.add": "Добавить",
  "common.edit": "Изменить",
  "common.close": "Закрыть",
  "common.dismiss": "Скрыть",
  "common.copy": "Копировать",
  "common.copied": "Скопировано",
  "common.never": "никогда",
  "common.empty": "пусто",

  // nav
  "nav.admin": "Админка",
  "nav.logout": "Выйти",
  "nav.theme.toLight": "Светлая тема",
  "nav.theme.toDark": "Тёмная тема",
  "nav.theme.toggle": "Сменить тему",

  // login
  "login.eyebrow.setup": "Первый запуск",
  "login.eyebrow.login": "Вход",
  "login.brand": "AI Tasker",
  "login.subtitle.setup": "Создайте аккаунт администратора для начала работы.",
  "login.subtitle.login": "Панель оператора для pull-агентов.",
  "login.usernameLabel": "Имя пользователя",
  "login.passwordLabel": "Пароль",
  "login.confirmLabel": "Повторите пароль",
  "login.usernamePlaceholder": "username",
  "login.error.shortPassword": "Пароль должен быть не короче 8 символов",
  "login.error.mismatch": "Пароли не совпадают",
  "login.error.failed": "Не удалось войти",
  "login.button.setup": "Создать администратора",
  "login.button.login": "Войти",

  // board
  "board.eyebrow": "Доска",
  "board.title": "Все задачи",
  "board.newTask": "+ Новая задача",
  "board.tip":
    "Перетаскивайте карточки между колонками. Бросьте в {ready}, чтобы сделать их доступными агентам через MCP.",
  "board.tipReady": "READY",

  // column
  "column.empty": "пусто",

  // status labels
  "status.todo": "Бэклог",
  "status.ready": "Готово",
  "status.in_progress": "В работе",
  "status.review": "Проверка",
  "status.acceptance": "Приёмка",
  "status.done": "Выполнено",
  "status.blocked": "Заблокировано",
  "status.cancelled": "Отменено",

  // task card
  "task.live": "активна",
  "task.reservedTooltip": "Зарезервировано для {agent}",
  "task.claimedBy": "взял {name}",
  "task.pr": "PR #{num}",
  "task.prFallback": "pr",

  // pr status
  "pr.merged": "слит",
  "pr.closed": "закрыт",
  "pr.open": "открыт",

  // card detail
  "card.back": "← К доске",
  "card.taskPrefix": "Задача #{id}",
  "card.reservedTooltip": "Зарезервировано для этого агента",
  "card.section.progress": "Прогресс",
  "card.section.details": "Детали",
  "card.noDescription": "Нет описания",
  "card.assignedTo": "Назначено",
  "card.assignAnyone": "Кому угодно (не назначено)",
  "card.assignTooltip":
    "Зарезервировать задачу за конкретным агентом. Другие не увидят её и не смогут взять.",
  "card.reopenReady": "Переоткрыть → ready",
  "card.cancel": "Отменить",
  "card.error.assign": "Не удалось назначить задачу",
  "card.error.update": "Не удалось обновить задачу",

  // comments
  "comment.heading": "Комментарии",
  "comment.empty": "Комментариев пока нет.",
  "comment.seen": "прочитано",
  "comment.pending": "ожидает",
  "comment.inputPlaceholder": "Комментарий для агента…",
  "comment.statusAfter": "Статус после отправки",
  "comment.toInProgress": "→ in_progress",
  "comment.toReady": "→ ready",
  "comment.sending": "Отправка…",
  "comment.error": "Не удалось отправить комментарий",

  // new task modal
  "newTask.eyebrow": "Новая задача",
  "newTask.title": "Создать задачу",
  "newTask.titleLabel": "Заголовок",
  "newTask.titlePlaceholder": "Что нужно сделать?",
  "newTask.descLabel": "Описание",
  "newTask.descPlaceholder": "Поддерживается Markdown",
  "newTask.tagsLabel": "Теги",
  "newTask.tagsPlaceholder": "через запятую",
  "newTask.repoLabel": "Путь к репозиторию (опц.)",
  "newTask.baseLabel": "Базовая ветка (опц.)",
  "newTask.assignLabel": "Назначить (опц.)",
  "newTask.assignTooltip":
    "Зарезервировать задачу за конкретным агентом. Другие не увидят её.",
  "newTask.assignAnyone": "Кому угодно (не назначено)",
  "newTask.creating": "Создание…",
  "newTask.create": "Создать задачу",
  "newTask.error": "Не удалось создать задачу",

  // progress feed
  "progress.collapseAll": "Свернуть все диффы",
  "progress.planning": "Изменение статуса",
  "progress.expandAll": "Развернуть все диффы",
  "progress.diff": "дифф",
  "progress.hunks": "{count} блок(ов)",

  // admin
  "admin.eyebrow": "Администрирование",
  "admin.title": "Токены и пользователи",
  "admin.tokensHeading": "Токены (агенты)",
  "admin.usersHeading": "Пользователи",
  "admin.banner": "Скопируйте сейчас — показан один раз",
  "admin.agentPlaceholder": "agent_name (напр. codex)",
  "admin.descPlaceholder": "описание (опц.)",
  "admin.mint": "Создать",
  "admin.col.agent": "Агент",
  "admin.col.description": "Описание",
  "admin.col.created": "Создан",
  "admin.col.lastUsed": "Посл. использование",
  "admin.col.role": "Роль",
  "admin.col.username": "Имя",
  "admin.noTokens": "Токенов пока нет.",
  "admin.revoke": "Отозвать",
  "admin.userPlaceholder": "username",
  "admin.passPlaceholder": "password",
  "admin.admin": "admin",
  "admin.role.admin": "админ",
  "admin.role.user": "пользователь",
  "admin.changePassBody":
    "Смена пароля — введите {your} текущий пароль администратора и новый пароль (8+) для {name}.",
  "admin.changePassYour": "свой",
  "admin.yourCurrentPass": "ваш текущий пароль",
  "admin.newPassFor": "новый пароль для {name}",
  "admin.changePassword": "Сменить пароль",
  "admin.promote": "Повысить до админа",
  "admin.demote": "Понизить",
  "admin.deleteUser": "Удалить пользователя",
  "admin.error.mint": "Не удалось создать токен",
  "admin.error.revoke": "Не удалось отозвать токен",
  "admin.error.addUser": "Не удалось добавить пользователя",
  "admin.error.removeUser": "Не удалось удалить пользователя",
  "admin.error.changePass": "Не удалось сменить пароль",
  "admin.error.adminFlag": "Не удалось изменить права администратора",
};

const CATALOGS: Record<Locale, Catalog> = { en, ru };

// ── Store ───────────────────────────────────────────────────────────────────

const STORAGE_KEY = "kanban-locale";

let _locale: Locale = getInitialLocale();
const _listeners = new Set<(l: Locale) => void>();

/** Resolve the initial locale: saved pref → browser language → en. */
export function getInitialLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "ru" || saved === "en") return saved;
  } catch {
    /* localStorage unavailable */
  }
  return "ru";
}

export function getLocale(): Locale {
  return _locale;
}

export function setLocale(next: Locale): void {
  if (next === _locale) return;
  _locale = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* ignore */
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = next;
  }
  for (const fn of _listeners) fn(next);
}

export function subscribe(fn: (l: Locale) => void): () => void {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}

// ── Translation functions ───────────────────────────────────────────────────

/** Translate `key`, interpolating `{param}` tokens from `params`. */
export function t(key: string, params?: Record<string, string | number>): string {
  const cat = CATALOGS[_locale] ?? en;
  let raw = cat[key] ?? en[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      raw = raw.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return raw;
}

/**
 * Pluralized translate. Russian has three forms (1 / 2–4 / 5+); English is
 * handled by the catalog's `{count}` token with an explicit "(s)" suffix.
 * We special-case the single plural key (`progress.hunks`) via a RU override.
 */
export function tCount(key: string, count: number): string {
  if (_locale === "ru") {
    const mod10 = count % 10;
    const mod100 = count % 100;
    let suffix: string;
    if (mod10 === 1 && mod100 !== 11) suffix = "";
    else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) suffix = "а";
    else suffix = "ов";
    // For progress.hunks: "{count} блок(ов)" → replace the (ов) variant.
    if (key === "progress.hunks") {
      return `${count} блок${suffix}`;
    }
  }
  return t(key, { count });
}

/** Map our locale to a BCP-47 tag for Intl APIs (toLocaleString etc.). */
export function localeBcp47(locale: Locale = _locale): string {
  return locale === "ru" ? "ru-RU" : "en-US";
}
