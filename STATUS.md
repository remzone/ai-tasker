# AI Tasker — статус

Обновлено: 5 октября 2026. **Минимальный рабочий продукт реализован и запущен.**

## Этап 1 — исходник и baseline
- Рабочий каталог: `/home/eshr/projects/personal/aitasker`.
- Основа: [graywrk/agent-kanban](https://github.com/graywrk/agent-kanban), commit `a59b3466b51dde08bf19448f55240b82953873e1`.
- Taskay изучен только для чтения: sidebar, проекты, карточки/формы и glass/blue theme. Файлы reference не изменялись.
- Исходный frontend успешно собран, исходный сервер проверен: HTTP 200.
- До изменений: **112 tests passed**, 4 upstream warnings.
- MIT LICENSE и copyright сохранены без изменений; исходные README/credits сохранены в docs/upstream.

## Этап 2 — UI
- AI Tasker branding только в интерфейсе; внутренние packages/modules/entities/env и существующие migrations не переименованы.
- Русский default через существующий i18n; переключение RU/EN сохранено.
- Sidebar, список проектов, создание проекта с repository/default branch.
- Главная страница проекта — Kanban с фильтром задач этого проекта и поиском.
- Шесть колонок: Бэклог → Готово → В работе → Проверка → Приёмка → Выполнено.
- Существующие blocked/cancelled записи доступны отдельно; внутренние статусы сохранены.
- Создание/редактирование задачи, description, acceptance criteria, tags, agent assignment.
- Вложения/скриншоты до 20 МБ, просмотр через существующий ArtifactCard и защищённый content endpoint.
- Progress, comments, diff, summary, AI review и история возвратов видны в задаче.
- Отдельная панель human acceptance с обязательным комментарием при возврате.
- Светлая/тёмная тема и мобильная навигация; desktop показывает все шесть колонок на ширине 1512px.

## Этап 3 — workflow/MCP
- Сохранены FastAPI/PostgreSQL/React, существующий MCP Streamable HTTP, bearer tokens и WebSocket.
- Приложение пассивно: не запускает Codex, не использует OpenAI API, OPENAI_API_KEY не требуется.
- Дополнен существующий workflow: acceptance status, criteria/summary/reviewer fields, одна новая migration 0005.
- Atomic conditional UPDATE для claim_task/claim_review; hard assignment проверяется в самом UPDATE, включая stale sessions.
- Row locks для решений/изменений; дублирующиеся review decisions отклоняются.
- 16 MCP tools. Добавлены list_projects, get_task_context, get_next_review, claim_review, submit_review.
- get_next_task/list_tasks поддерживают project_id; возвращённые unclaimed in_progress задачи доступны для повторного claim.
- Context включает repo/base branch, criteria, comments, attachments, summary, progress и решения; агент читает AGENTS.md/skills непосредственно в repository.
- REQUEST_CHANGES → В работе; APPROVE → Приёмка; замечания обязательны и сохранены.
- После возврата от reviewer/человека исполнитель освобождается для нового claim; hard assignment сохраняется.
- Только человек с session cookie может принять задачу → Done. PATCH, комментарии и progress агента не обходят review/acceptance.
- Старый complete_task совместимо отправляет на review. Summary для отправки на review обязателен.
- Обычный комментарий не меняет workflow.
- Исправлен upstream bug: CLI migrate теперь читает DATABASE_URL из .env так же, как serve.
- REST timestamps включают UTC Z; для файлов поддержан HEAD.

## Этап 4 — проверки завершены
- Финальный полный suite: **118 passed**, 4 upstream warnings; `.runtime/final-tests.log`.
- После последней правки комментариев/concurrency: **8 targeted tests passed**; `.runtime/last-checks.log`.
- Ruff backend/new migration и git diff --check: успешны.
- Frontend TypeScript + production build: успешны. Frontend lint: без errors, имеются warnings существующего React/i18n pattern. Build сохраняет upstream Shiki chunk-size warning.
- Реальный HTTP MCP с настоящими bearer tokens: полный workflow, повторные возвраты, запрещённые обходы, identity/claim checks, history и attachments.
- PostgreSQL concurrency: одновременно два work claims / два review claims / два review decisions; успешен только один. Проверен stale assignment.
- Проверены project-scoped discovery, inherited repo/branch, comments UTC, screenshot/HEAD, upload size limit и cleanup.
- Chromium: Project → Task/upload/edit → Готово → MCP claim → реальные файлы/commits → request_review/git diff → REQUEST_CHANGES → доработка → APPROVE → human RETURN → повторная доработка/APPROVE → human ACCEPT → Done.
- UI проверен через реальные HTTP MCP вызовы, без stubs/mock transport; выполнение работы воспроизводилось тестовым драйвером, не запуском Codex из приложения.
- Browser проверил drag-and-drop Бэклог → Готово, mobile sidebar, отсутствие горизонтального overflow списка проектов и обе темы; JavaScript errors: **0**.
- Проверочный результат: `.runtime/browser-result.json`, журнал `.runtime/browser-smoke.log`.
- Скриншоты: `.runtime/kanban-desktop.png`, `.runtime/acceptance-desktop.png`, `.runtime/projects-mobile.png`, `.runtime/projects-light.png`.
- Smoke выполнялся на отдельной базе aitasker_ui_smoke и repository внутри .runtime. Тестовый сервер 7332 остановлен.
- Stop/start приложения и локального PostgreSQL проверен; основной сервер перезапущен с последним кодом.

## Запуск и ваши следующие действия
- **http://localhost:7331** — основной сервер, новая UTF8 база, первый аккаунт создаётся через UI.
- `./scripts/start-local.sh` / `./scripts/stop-local.sh` — запуск/остановка с сохранением данных.
- Все локальные инструменты (.tools), БД/uploads/logs (.runtime), dependencies (.venv) и приватный .env находятся внутри проекта и исключены из git/Docker context.
- Создайте своего администратора и MCP токен в «Настройки и MCP».
- Подключение личного Codex из VS Code: README.md и docs/codex-mcp.example.toml. В вашем глобальном Codex config ничего не изменялось; подключить токен нужно в вашем IDE.
- Точное подключение вашего уже запущенного VS Code не проверялось; проверен сервер и протокол через реальный MCP client.
- Docker configuration сохранена и обновлена (Node 22, git для diff, persisted artifact volume); Docker build/run не проверялся, так как Docker Desktop недоступен в этом WSL. Рабочий локальный запуск проверен.
- Для контейнерного доступа к host repository нужен bind mount по тому же абсолютному repo_path; для текущего сценария используется непосредственный WSL запуск.

## Исправление авторизации MCP после подключения Codex
- Воспроизведена точная ошибка `authentication required (Bearer token)`: initialize без авторизации, последующий tools/call с действующим bearer всё равно отклонялся.
- Причина: долгоживущий MCP session task наследовал ContextVar первого запроса. Последующие заголовки не меняли principal инструмента; также мог сохраняться ранее авторизованный principal при отсутствии/смене токена.
- Middleware теперь сохраняет principal в scope текущего HTTP Request. Verifiers читают Request из per-message request_ctx SDK. Для HTTP нет fallback на session ContextVar; прямые in-process проверки сохраняют прежний тестовый контекст.
- Три новых regression tests до исправления падали; после исправления весь модуль HTTP MCP: 6 passed. Ruff и git diff --check успешны.
- Исправление требует перезапуска фактически запущенного backend и нового подключения MCP. На момент диагностики сохранённый app.pid уже не существует, хотя порт 7331 отвечает; текущий процесс не определён, поэтому его перезапуск не выполнен.
- Полный backend suite после исправления: **121 passed**, 4 dependency warnings, журнал `.runtime/auth-fix-tests.log`.

## Применение исправления к Docker
- После уточнения пользователя обнаружен доступный Docker Compose: app работал со старым кодом (`per_request_auth: False`), несмотря на restart.
- Выполнено `docker compose up -d --build app`; образ пересобран, контейнер app пересоздан. PostgreSQL и существующие volumes сохранены.
- В новом контейнере `per_request_auth: True`.
- Реальные HTTP MCP вызовы в работающий backend: anonymous initialize → действующий bearer → list_projects/list_tasks успешно; без bearer в той же сессии вызов отклонён.
- Для диагностики использован временный токен, удалённый в finally; пользовательские задачи не изменялись и не брались в работу.
- При прямом Authorization header поле bearer token env var следует оставить пустым; после сохранения настроек клиенту требуется новое подключение MCP.

## Повторная диагностика текущего подключения Codex
- Прочитаны настройки tasker в локальном Codex config без вывода секрета: URL корректен, bearer_token_env_var отсутствует, Authorization имеет Bearer prefix и не содержит внешних пробелов.
- Точный сохранённый токен безопасно передан через stdin в диагностический процесс Docker, без вывода или записи plaintext.
- _resolve_bearer в текущей Docker базе вернул None: сохранённый токен недействителен для этого экземпляра (3 существующих token records).
- Реальный HTTP list_projects с этим же заголовком вернул isError=True. Требуется заменить токен в пользовательском MCP подключении на новый, созданный через UI работающего Docker экземпляра.
- Глобальный config не изменялся, существующие токены и пользовательские задачи не изменялись.

## Готовый конфиг для устранения повторной ошибки подключения
- WSL config по-прежнему содержит недействующий токен. После повторной жалобы новых tools/call от внешнего клиента в просмотренных Docker логах не найдено; конкретный клиент пользователя ещё уточняется.
- Создан отдельный действующий токен codex с описанием Codex connection repair. Приватный конфиг сохранён только внутри проекта: .runtime/tasker-mcp.toml, права 0600, исключён из git.
- Токен из готового конфига проверен по Docker базе и реальными HTTP MCP list_projects/list_tasks: успешно. Задачи не брались и не изменялись.
- Пользовательские глобальные конфиги не изменялись. Готовый блок нужно применить в конфигурации фактического клиента Codex вместо существующего блока tasker.

## Управление токенами на сайте: повторный показ и копирование
- По запросу пользователя выбран вариант генерации отдельных токенов для каждого агента в UI с повторным показом и копированием.
- Новая миграция c3d4e5f6a7b8 добавляет nullable token.token_ciphertext; существующие агенты и токены сохраняются.
- Новые и заменённые токены сохраняются зашифрованными Fernet; отдельный ключ выведен domain-separated HMAC-SHA256 из SESSION_SECRET. Bcrypt-хеш остаётся источником проверки bearer.
- Только human admin может POST reveal/regenerate; секретные ответы имеют Cache-Control: no-store. Список токенов не содержит plaintext/ciphertext, возвращает лишь can_reveal.
- Старые hash-only токены требуют явной генерации замены. Замена сохраняет agent_name/description, сбрасывает last_used_at и немедленно отключает старое значение; UI предупреждает перед этим действием. Смена SESSION_SECRET не отключает bearer-проверку, но требует замены для повторного показа.
- UI: показать/скрыть значение, закрыть панель, копировать токен/Authorization/готовый tasker config, повторно открыть после refresh, заменить и отозвать.
- Кнопка «Проверить MCP» выполняет реальные HTTP initialize/initialized/list_projects/list_tasks с credentials: omit, строго по bearer; затем закрывает MCP-сессию. Проверка не берёт задачи и не изменяет workflow.
- README и docs/codex-mcp.example.toml теперь описывают прямое копирование проверенного config; env-вариант остаётся документированной альтернативой.
- Cryptography добавлена как явная dependency, uv.lock обновлён.
- Тесты token/auth/MCP: 31 passed. Полный backend suite: **126 passed**, 4 dependency warnings; .runtime/token-full-tests.log.
- Ruff, git diff --check, frontend TypeScript/production build успешны; frontend lint без errors, существующие React warnings.
- Docker app пересобран и пересоздан, новая миграция применена, существующие PostgreSQL/artifacts volumes сохранены.
- Браузер работающего Docker: create/reveal/hide/copy token/header/config/reload/replace (old bearer 401/new bearer 200)/revoke, реальные MCP read calls и mobile overflow успешно; JS errors 0.
- Проверка использовала только временного тестового агента, удалённого после выполнения. Пользовательские задачи и существующие токены не менялись.
- Артефакты: .runtime/token-ui-browser-result.json, .runtime/token-ui-desktop.png, .runtime/token-ui-mobile.png; скриншоты содержат скрытое значение токена.
- Точная сессия пользовательского Codex не проверялась; требуется заменить её tasker config и пересоздать подключение.

## Диагностика живого Codex MCP: Docker Desktop + WSL
- После доступности реальных mcp__tasker инструментов воспроизведена ошибка непосредственно через MCP текущего Codex, а не только проверочным клиентом.
- Текущий токен ~/.codex/config.toml действителен для текущей Docker БД; прямой вызов и полноценный MCP SDK client из WSL успешно выполняют list_projects/list_tasks.
- codex mcp get tasker --json читает тот же transport/URL/http_headers, что и текущий файл; проектных переопределений в проверенных расположениях не найдено.
- Добавлены безопасные категории auth errors: Authorization header is missing / malformed Bearer / Bearer token is invalid or revoked. Значения заголовков и токенов не выводятся. Уточнён устаревший комментарий server.py про ContextVar.
- Реальный вызов текущего Codex после обновления Docker вернул Bearer token is invalid or revoked: заголовок доходит, но содержит недействующий токен; текущий токен на диске успешно проверен стандартным MCP SDK.
- Живой codex app-server запущен 2026-10-05 09:10:34 UTC, config изменён 12:57:05 UTC: процесс предшествует изменениям настроек. Требуется перезапуск именно процесса расширения (VS Code Developer: Reload Window / Restart extension) и новый чат.
- Сеть WSL → Docker подтверждена реальным MCP SDK, ошибка не связана с файловыми правами или недоступностью порта.
- MCP HTTP и in-process tests после диагностической правки: 31 passed; Ruff и diff check успешны. Docker образ обновлён. Пользовательские токены и задачи не менялись.

## Вставка скриншотов Ctrl+V в описание задачи
- Добавлена обработка clipboard image files в поле описания NewTaskModal: при создании и редактировании задачи изображения вставляются в текущую позицию курсора, заменяя выделенный текст.
- Обычный текстовый paste остаётся стандартным. Скриншоты получают имя screenshot-* и ограничены 20 МБ на файл.
- До сохранения доступен локальный предпросмотр; object URLs освобождаются при закрытии формы. Отмена новой формы не загружает файлы и не создаёт задачу.
- При сохранении изображения загружаются существующим API attachments; временные ссылки заменяются постоянными /api/artifacts/{id}/content в Markdown description. В карточке изображения показываются прямо в тексте, доступны как вложения и остаются в MCP task context.
- Успешные загрузки кэшируются в форме; повторная попытка после частичной ошибки не создаёт дубликаты изображения или задачи. Скриншот, удалённый из текста до сохранения, не загружается.
- Добавлены RU/EN подсказка и сообщения. Изображения Markdown ограничены шириной текстовой колонки; предпросмотр прокручивается.
- TypeScript/production build успешны, frontend lint без errors (существующие warnings), git diff --check успешен.
- Docker app пересобран и пересоздан; PostgreSQL/artifact volumes и пользовательские данные сохранены.
- Проверено реальными ClipboardItem + Control+V в Chromium: создание, позиция курсора, обычный текст, редактирование/несколько изображений, ошибка второй загрузки и retry, отсутствие дубликатов, показ после reload, mobile overflow. JS errors: 0.
- Проверка выполнялась на отдельном временном проекте, который вместе с задачей и загруженными файлами удалён после проверки. Пользовательские задачи не изменялись.
- Артефакты: .runtime/paste-browser-result.json, .runtime/paste-task-desktop.png, .runtime/paste-task-mobile.png.

## Исправление канбана, назначаемое AI-ревью и ручная приёмка
- Пользователь запросил перенос в Готово и выбор между ревью агентом и приёмкой человеком. Новое правило: человек может лично принять результат из in_progress/review/acceptance; агентские токены закрывать задачу по-прежнему не могут.
- Добавлен отдельный session-only POST /api/tasks/{id}/workflow (ready/start/review/human_review/accept/return). Решения выполняются под row lock и сохраняются в progress/history/comments с actor user:{user_id}; возвращение требует замечаний.
- Перенос в Готово атомарно освобождает исполнителя/reviewer/назначение ревью; hard assignment рабочего агента сохраняется. Ручной старт доступен из ready. Обычный PATCH сохраняет прежние ограничения и не обходится агентами.
- Миграция d4e5f6a7b8c9 добавляет review_assigned_to отдельно от атомарного review claim. Назначение проверяет действующий токен агента; get_next_review скрывает чужие назначения, claim_review отклоняет других агентов.
- WorkflowPanel в карточке и диалоге drop: описание результата, выбранный reviewer, отправка агенту/человеку, ручное принятие, возврат с обязательным комментарием. Выбор агента не запускает Codex автоматически; reviewer работает через MCP.
- Kanban больше не делает ошибочные optimistic переходы перед сервером. Проверены ID drop, same-status noop; drop review/done открывает явное решение, drop acceptance инициирует человеческую проверку. Карточка показывает назначение ревьюера.
- Полный backend suite: **127 passed**, 4 dependency warnings; .runtime/human-workflow-tests.log. Новый настоящий HTTP MCP test покрывает manual start/requeue, stale worker rejection, reviewer assignment/discovery/claim/approve, bearer denial для human endpoint, return/direct human accept и историю.
- Ruff, TypeScript production build, git diff --check успешны; frontend lint без errors, существующие warnings.
- Docker образ собран, app пересоздан, миграция применена; данные и volumes сохранены.
- Chromium работающего Docker: настоящие drag/drop todo→ready→in_progress→ready; drop review → выбор агента; чужой reviewer отклонён; назначенный reviewer claim/APPROVE через реальный MCP; ручная приёмка → done; reopen/requeue → ручная проверка → return; drop Done → подтверждение ручной приёмки. История и mobile overflow проверены, JS errors 0.
- Проверка использовала отдельный временный проект/задачу и два временных токена; все эти записи удалены после проверки. Пользовательские задачи и токены не изменялись.
- Артефакты: .runtime/workflow-browser-result.json, .runtime/workflow-review-desktop.png, .runtime/workflow-review-mobile.png. README обновлён под текущие человеческие действия.

## 2026-10-05 — Ограничения проекта/задачи и полный промпт

- Миграция e5f6a7b8c9d0 добавляет agent_instructions проекта и задачи, старые записи получают пустую строку. Ограничения проекта наследуются динамически при чтении контекста; собственные инструкции задачи хранятся отдельно.
- Новый human-only PATCH /api/projects/{id}: имя, repo_path, branch и инструкции. Существующий human-only PATCH задач сохраняет инструкции и отклоняет null. Bearer агент может читать, но не менять правила существующего проекта/задачи.
- REST /api/tasks/{id}/context и MCP get_task_context возвращают project_agent_instructions, agent_instructions, effective_agent_instructions, agent_prompt. Полный промпт включает repo, чтение AGENTS.md, обе группы правил, описание, критерии, комментарии, вложения, результат для ревью и требования финального отчёта. MCP server instructions требуют прочитать контекст перед исполнением и ревью.
- На доске добавлены Настройки проекта. Общий шаблон ограничений и шаблон Odyssey добавляются без удаления существующего текста; пути берутся из репозитория проекта. Шаблон Odyssey повторяет предоставленные пользователем ограничения: только bundles/Odyssey, инфраструктура readonly, запрет Kafka/rdkafka, разрешённые existing Docker-действия, React/Rsbuild/i18n, backend DI/API/security, диагностика OpenSearch/GDI, отчёт и остановка при необходимости выхода за scope.
- Создание проекта поддерживает общие инструкции. Создание/изменение задачи поддерживает дополнительные ограничения, показывает наследуемые правила и добавляет структуру постановки задачи/критериев. Явные доступные подписи textarea исправляют подпись уже заполненных полей.
- Карточка показывает правила и предлагает Полный промпт для агента с просмотром, копированием и Ctrl+C. При открытии берётся актуальный контекст, включая последние изменения проекта. Интерфейс объясняет: текстовые инструкции не заменяют файловый sandbox внешнего Codex.
- Полный backend suite: **130 passed**, 4 предупреждения зависимостей; .runtime/instructions-full-tests.log. Ruff, TypeScript/production build, git diff --check успешны. Frontend lint без errors, прежние warnings; новый warning о порядке объявления setError устранён.
- Docker image пересобран, app пересоздан, миграция применена. Браузер: создание проекта, настройки/шаблон Odyssey, сохранение правил, шаблон задачи без потери текста, наследование, редактирование, полный промпт и системный clipboard, новые правила проекта в уже существующей задаче, worker/reviewer через HTTP MCP, reload persistence, мобильный prompt без overflow; JS errors 0.
- Проверка использовала собственный временный проект, задачу и два токена; после проверки записи удалены. Пользовательские проекты, задачи и токены не менялись. Исходные изменения только в aitasker; SD/Odyssey не менялся.
- Артефакты: .runtime/instructions-browser-result.json, .runtime/instructions-prompt-desktop.png, .runtime/instructions-prompt-mobile.png. README обновлён.


## Публикация AI Tasker — 2026-10-05

- Новый публичный репозиторий: https://github.com/remzone/ai-tasker. Original graywrk/agent-kanban сохранён как upstream; история и MIT LICENSE сохранены.
- README содержит Docker quickstart, Windows/PowerShell вариант, управление данными, настройки порта, mounts репозиториев и основные отличия от оригинала.
- scripts/start-docker.sh создаёт .env.docker с криптографически случайным SESSION_SECRET один раз, собирает приложение и ожидает healthcheck. Runtime использует frozen uv.lock без dev-зависимостей; fallback установки без lock удалён.
- Старые иллюстрации заменены тремя снимками текущего русского интерфейса SD: Kanban, результат/приёмка задачи и вход. Снимки сделаны из существующего приложения без изменений задач.
- Проверки: pytest — 130 passed; ruff — passed; production frontend build — passed (предупреждение Vite о крупных chunks); browser screenshots — без page errors.
- Изолированное Docker-окружение с чистыми volumes: migrations, healthchecks, первый администратор, login, frontend и API passed. После down/up администратор сохранён. Отдельно проверены quickstart без .env и повторный запуск с сохранением SESSION_SECRET.
- Локальные .env, .env.docker, .runtime, .tools, .venv, node_modules и данные PostgreSQL исключены из Git и Docker build context.
