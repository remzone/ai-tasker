import { useEffect, useState } from "react";
import { api } from "../api";
import type { OpenRouterBalance } from "../api";
import { useT } from "../i18n.tsx";

export function OpenRouterSettings() {
  const { locale } = useT();
  const ru = locale === "ru";
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [managementKey, setManagementKey] = useState("");
  const [hasManagementKey, setHasManagementKey] = useState(false);
  const [hasKey, setHasKey] = useState(false);
  const [balance, setBalance] = useState<OpenRouterBalance | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.openRouterSettings().then(value => { setModel(value.model); setHasKey(value.has_key); setHasManagementKey(value.has_management_key); if (value.has_key) api.openRouterBalance().then(setBalance).catch(e => setError(String(e))); }).catch(e => setError(String(e))); }, []);
  async function save(clear = false, clearManagement = false) {
    setBusy(true); setError(""); setMessage("");
    try {
      const value = await api.saveOpenRouter({ model, api_key: key || undefined, clear_key: clear, management_key: managementKey || undefined, clear_management_key: clearManagement });
      setHasKey(value.has_key); setHasManagementKey(value.has_management_key); setKey(""); setManagementKey(""); setBalance(null);
      setMessage(ru ? "Настройки сохранены" : "Settings saved");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function refreshBalance() {
    setBusy(true); setError("");
    try { setBalance(await api.openRouterBalance()); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <div>
    <h3>OpenRouter</h3>
    <p className="muted">{ru ? "Помощь в подготовке ТЗ и критериев приёмки. Текст задачи отправляется выбранной модели только по нажатию кнопки генерации." : "Draft specifications and acceptance criteria. Task text is sent to the selected model when you request generation."}</p>
    <label>{ru ? "Модель OpenRouter" : "OpenRouter model"}<input className="input" value={model} disabled={busy} onChange={e => setModel(e.target.value)} placeholder="provider/model" /></label>
    <label>{ru ? "API-ключ" : "API key"}<input className="input" type="password" autoComplete="new-password" value={key} disabled={busy} onChange={e => setKey(e.target.value)} placeholder={hasKey ? (ru ? "Ключ сохранён; пустое поле сохраняет текущий" : "Key saved; leave blank to keep it") : "sk-or-…"} /></label>
    <label>{ru ? "Management-ключ для баланса аккаунта (необязательно)" : "Management key for account balance (optional)"}<input className="input" type="password" autoComplete="new-password" value={managementKey} disabled={busy} onChange={e => setManagementKey(e.target.value)} placeholder={hasManagementKey ? (ru ? "Ключ сохранён" : "Key saved") : "sk-or-…"} /></label>
    <div className="form-actions">
      <button className="btn btn-primary" disabled={busy || !model.trim()} onClick={() => save()}>{ru ? "Сохранить" : "Save"}</button>
      <button className="btn" disabled={busy || !hasKey} onClick={refreshBalance}>{ru ? "Обновить баланс" : "Refresh balance"}</button>
      <button className="btn" disabled={busy || !hasKey || !model.trim()} onClick={() => save(true)}>{ru ? "Удалить ключ" : "Remove key"}</button>
      <button className="btn" disabled={busy || !hasManagementKey || !model.trim()} onClick={() => save(false, true)}>{ru ? "Удалить management-ключ" : "Remove management key"}</button>
    </div>
    {balance && <p role="status">{ru ? "Баланс аккаунта" : "Account balance"}: {balance.balance === null ? (ru ? "недоступен для этого ключа" : "unavailable for this key") : `$${balance.balance.toFixed(4)}`}<br />{ru ? "Остаток лимита ключа" : "Key limit remaining"}: {balance.key_remaining === null ? (ru ? "без лимита" : "unlimited") : `$${balance.key_remaining.toFixed(4)}`}<br />{ru ? "Использовано ключом" : "Key usage"}: {balance.usage === null ? "—" : `$${balance.usage.toFixed(4)}`}</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="error-banner">{error}</p>}
  </div>;
}
