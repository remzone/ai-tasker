import type { Locale } from "./i18n";

export function taskTemplate(locale: Locale): string {
  return locale === "ru" ? `Задача:
[кратко опиши требуемый результат]

Тип задачи:
[backend / frontend / full-stack]

Где проявляется:
[URL/route, экран, файл или компонент]

Текущее поведение:
[ошибка, HTTP status, stack trace, Console/Network, шаги воспроизведения]

Ожидаемое поведение:
[что должен увидеть пользователь или получить API]

Данные для воспроизведения:
[ID, payload, роль пользователя; секреты не вставлять]` : `Task:
[required result]

Task type:
[backend / frontend / full-stack]

Location:
[URL/route, screen, file or component]

Current behavior:
[error, HTTP status, stack trace, Console/Network, reproduction steps]

Expected behavior:
[user-visible result or API response]

Reproduction data:
[IDs, payload, user role; do not include secrets]`;
}

export function projectTemplate(repo: string, locale: Locale, odyssey = false): string {
  if (odyssey) {
    const path = repo.trim() || "/home/eshr/projects/pimcore/SD";
    return `Перед началом полностью прочитай:
- ${path}/AGENTS.md
- ${path}/bundles/Odyssey/AGENTS.md
- все более вложенные AGENTS.md, относящиеся к изменяемым файлам.

Жёсткое ограничение: изменять, создавать, перемещать и удалять исходные файлы можно только внутри ${path}/bundles/Odyssey. Вся инфраструктура и всё вне этой директории только для чтения. Не меняй docker-compose.yaml, docker/, .docker/, config/, .env*, корневые composer-файлы, vendor/ и bundles/Pimcore. Не устанавливай и не настраивай Kafka/rdkafka.
Существующие Docker-сервисы разрешено использовать для диагностики, сборки, тестов, миграций и проверки результата. Не делай commit/push без отдельной просьбы.

Самостоятельно воспроизведи и диагностируй проблему, затем реализуй минимальный фикс строго в Odyssey bundle. Для frontend используй существующий React/Rsbuild, компоненты, токены и i18n; после изменения выполни релевантные тесты и npm run build. Для backend следуй существующим DI/API/security-паттернам и запусти узкие тесты. Если затронут OpenSearch/GDI, не отключай индексацию и не маскируй BulkOperationException: найди конкретный index/element и item-level причину, затем проверь исходный API endpoint.

В финале сообщи причину проблемы, список изменённых файлов, что исправлено, выполненные тесты/сборки и их результат, runtime-действия с Docker, БД или OpenSearch, оставшиеся риски и подтверждение, что исходные изменения находятся только в bundles/Odyssey и посторонние изменения не затронуты.

Если исправление объективно требует файла вне bundles/Odyssey, остановись, назови этот файл и объясни причину — не изменяй его самостоятельно.`;
  }
  return locale === "ru" ? `Перед началом прочитай корневой AGENTS.md и все вложенные AGENTS.md, относящиеся к изменяемым файлам.

Разрешённая область изменений:
[укажи абсолютный путь внутри ${repo || "репозитория"}]

Только для чтения / запрещено изменять:
[директории, файлы, инфраструктура]

Разрешённые runtime-действия:
[диагностика, существующие Docker-сервисы, тесты, сборки; ограничения на БД/миграции]

Не делай commit/push без отдельной просьбы.
Самостоятельно воспроизведи проблему и реализуй минимальный фикс. Используй существующие паттерны проекта.

Обязательные проверки:
[команды тестов и сборки]

Если нужны изменения вне разрешённой области, остановись, назови файл и объясни причину — не изменяй его самостоятельно.` : `Read root AGENTS.md and all nested AGENTS.md applicable to changed files before starting.

Allowed file scope:
[absolute directory inside ${repo || "the repository"}]

Read-only / prohibited changes:
[directories, files, infrastructure]

Allowed runtime actions:
[diagnostics, existing Docker services, tests, builds; database/migration limits]

Do not commit/push unless explicitly requested.
Reproduce the issue and implement a minimal fix using existing project patterns.

Required verification:
[test and build commands]

If changes outside the allowed scope are required, stop, identify the file and explain why; do not modify it yourself.`;
}
