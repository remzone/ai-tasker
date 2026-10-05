import { useEffect, useState } from "react";
import { api } from "../api";
import { useT, localeBcp47 } from "../i18n.tsx";

interface TokenRow {
  id: number;
  can_reveal: boolean;
  agent_name: string;
  description: string | null;
  created_at: string;
  last_used_at: string | null;
}
interface UserRow {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
}

export function Admin({ onBack }: { onBack: () => void }) {
  const { t, locale } = useT();
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [newTokenAgent, setNewTokenAgent] = useState("");
  const [newTokenDesc, setNewTokenDesc] = useState("");
  const [mintedToken, setMintedToken] = useState<{ id: number; token: string; agent_name: string } | null>(null);
  const [tokenVisible, setTokenVisible] = useState(false);
  const [tokenBusy, setTokenBusy] = useState(false);
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [newUser, setNewUser] = useState({ username: "", password: "", is_admin: false });
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);

  async function refresh() {
    setTokens(await api.listTokens());
    setUsers(await api.listUsers());
  }
  useEffect(() => {
    refresh();
  }, []);

  async function mint() {
    if (!newTokenAgent.trim()) return;
    setActionError(null);
    try {
      const tk = await api.createToken(newTokenAgent, newTokenDesc || undefined);
      setMintedToken(tk);
      setTokenVisible(false);
      setCheckResult(null);
      setNewTokenAgent("");
      setNewTokenDesc("");
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("admin.error.mint"));
    }
  }
  async function revoke(id: number) {
    setActionError(null);
    try {
      await api.deleteToken(id);
      if (mintedToken?.id === id) setMintedToken(null);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("admin.error.revoke"));
    }
  }
  async function openToken(tk: TokenRow, regenerate = false) {
    if (regenerate && !window.confirm(t("admin.replaceConfirm"))) return;
    setActionError(null);
    setTokenBusy(true);
    setCheckResult(null);
    try {
      const value = regenerate ? await api.regenerateToken(tk.id) : await api.revealToken(tk.id);
      setMintedToken({ id: tk.id, ...value });
      setTokenVisible(false);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("admin.error.mint"));
    } finally {
      setTokenBusy(false);
    }
  }
  async function copyText(text: string) {
    try {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const field = document.createElement("textarea");
        field.value = text;
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        try {
          field.select();
          if (!document.execCommand("copy")) throw new Error(t("admin.copyError"));
        } finally {
          field.remove();
        }
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setActionError(t("admin.copyError"));
    }
  }
  async function checkToken() {
    if (!mintedToken) return;
    setTokenBusy(true);
    setCheckResult(null);
    try {
      await api.checkMcpToken(mintedToken.token);
      setCheckResult(t("admin.checkSuccess"));
      await refresh();
    } catch (e) {
      setCheckResult(e instanceof Error ? e.message : t("admin.checkFailed"));
    } finally {
      setTokenBusy(false);
    }
  }
  const mcpConfig = mintedToken ? `[mcp_servers.tasker]
url = ${JSON.stringify(`${location.origin}/mcp`)}

[mcp_servers.tasker.http_headers]
Authorization = ${JSON.stringify(`Bearer ${mintedToken.token}`)}` : "";

  async function addUser() {
    if (!newUser.username || !newUser.password) return;
    setActionError(null);
    try {
      await api.createUser(newUser.username, newUser.password, newUser.is_admin);
      setNewUser({ username: "", password: "", is_admin: false });
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("admin.error.addUser"));
    }
  }
  async function removeUser(id: number) {
    setActionError(null);
    try {
      await api.deleteUser(id);
      if (editingUserId === id) setEditingUserId(null);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("admin.error.removeUser"));
    }
  }

  return (
    <div style={{ padding: "20px 20px 40px", maxWidth: 960, margin: "0 auto" }}>
      <button className="btn btn-ghost btn-sm" onClick={onBack} style={{ marginBottom: 16 }}>
        {t("common.backToBoard")}
      </button>
      <div className="eyebrow" style={{ marginBottom: 4 }}>{t("admin.eyebrow")}</div>
      <h1 style={{ marginBottom: 20 }}>{t("admin.title")}</h1>

      {actionError && (
        <div className="badge badge-error" style={{ marginBottom: 16, width: "100%" }}>
          {actionError}
        </div>
      )}

      <section className="panel">
        <h3>{t("admin.mcpTitle")}</h3>
        <p className="muted">{t("admin.mcpHint")}</p>
        <p className="muted">{t("admin.mcpSteps")}</p>
      </section>
      {/* Tokens */}
      <section style={{ marginBottom: 32 }}>
        <h3 style={{ marginBottom: 12 }}>{t("admin.tokensHeading")}</h3>

        {mintedToken && (
          <div className="panel" style={{ borderColor: "var(--accent)", marginBottom: 14 }}>
            <h3>{t("admin.tokenFor")} <span className="mono">{mintedToken.agent_name}</span></h3>
            <input className="input mono" aria-label={t("admin.agentToken")} type={tokenVisible ? "text" : "password"}
              value={mintedToken.token} readOnly autoComplete="off" spellCheck={false} style={{ width: "100%" }} />
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-sm" onClick={() => setTokenVisible(!tokenVisible)}>{t(tokenVisible ? "admin.hideToken" : "admin.showToken")}</button>
              <button className="btn btn-sm" onClick={() => copyText(mintedToken.token)}>{t("admin.copyToken")}</button>
              <button className="btn btn-sm" onClick={() => copyText(`Bearer ${mintedToken.token}`)}>{t("admin.copyHeader")}</button>
              <button className="btn btn-primary btn-sm" onClick={() => copyText(mcpConfig)}>{t("admin.copyConfig")}</button>
              <button className="btn btn-sm" disabled={tokenBusy} onClick={checkToken}>{t(tokenBusy ? "admin.checking" : "admin.checkMcp")}</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setMintedToken(null); setCheckResult(null); }}>{t("admin.closeToken")}</button>
            </div>
            {copied && <p role="status">{t("common.copied")}</p>}
            {checkResult && <p role="status" style={{ overflowWrap: "anywhere" }}>{checkResult}</p>}
            <p className="muted">{t("admin.configHint")}</p>
            <p className="muted">{t("admin.agentArgument")} <code>{JSON.stringify(mintedToken.agent_name)}</code></p>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <input
            className="input"
            placeholder={t("admin.agentPlaceholder")}
            value={newTokenAgent}
            onChange={(e) => setNewTokenAgent(e.target.value)}
            style={{ flex: "1 1 180px" }}
          />
          <input
            className="input"
            placeholder={t("admin.descPlaceholder")}
            value={newTokenDesc}
            onChange={(e) => setNewTokenDesc(e.target.value)}
            style={{ flex: "1 1 220px" }}
          />
          <button className="btn btn-primary" onClick={mint} disabled={!newTokenAgent.trim()}>
            {t("admin.mint")}
          </button>
        </div>

        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-small)" }}>
            <thead>
              <tr style={{ background: "var(--elevated)" }}>
                <Th>{t("admin.col.agent")}</Th>
                <Th>{t("admin.col.description")}</Th>
                <Th>{t("admin.col.created")}</Th>
                <Th>{t("admin.col.lastUsed")}</Th>
                <Th align="right"> </Th>
              </tr>
            </thead>
            <tbody>
              {tokens.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted" style={{ padding: 14, textAlign: "center" }}>
                    {t("admin.noTokens")}
                  </td>
                </tr>
              )}
              {tokens.map((tk) => (
                <tr key={tk.id} style={{ borderTop: "1px solid var(--border-soft)" }}>
                  <Td><span className="mono">{tk.agent_name}</span></Td>
                  <Td className="muted">{tk.description ?? "—"}</Td>
                  <Td className="muted">{fmt(tk.created_at, locale)}</Td>
                  <Td className="muted">
                    {tk.last_used_at ? (
                      fmt(tk.last_used_at, locale)
                    ) : (
                      <span className="badge badge-neutral">{t("common.never")}</span>
                    )}
                  </Td>
                  <Td align="right">
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                    {tk.can_reveal && <button className="btn btn-sm" disabled={tokenBusy} onClick={() => openToken(tk)}>{t("admin.openToken")}</button>}
                    <button className="btn btn-sm" disabled={tokenBusy} onClick={() => openToken(tk, true)}>{t(tk.can_reveal ? "admin.replaceToken" : "admin.generateToken")}</button>
                    <button className="btn btn-danger btn-sm" onClick={() => revoke(tk.id)}>
                      {t("admin.revoke")}
                    </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Users */}
      <section>
        <h3 style={{ marginBottom: 12 }}>{t("admin.usersHeading")}</h3>
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
          <input
            className="input"
            placeholder={t("admin.userPlaceholder")}
            value={newUser.username}
            onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
            style={{ flex: "1 1 160px" }}
          />
          <input
            className="input"
            type="password"
            placeholder={t("admin.passPlaceholder")}
            value={newUser.password}
            onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
            style={{ flex: "1 1 160px" }}
          />
          <label className="eyebrow" style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={newUser.is_admin}
              onChange={(e) => setNewUser({ ...newUser, is_admin: e.target.checked })}
            />
            {t("admin.admin")}
          </label>
          <button className="btn btn-primary" onClick={addUser}>
            {t("common.add")}
          </button>
        </div>

        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-small)" }}>
            <thead>
              <tr style={{ background: "var(--elevated)" }}>
                <Th>{t("admin.col.username")}</Th>
                <Th>{t("admin.col.role")}</Th>
                <Th>{t("admin.col.created")}</Th>
                <Th align="right"> </Th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRowView
                  key={u.id}
                  user={u}
                  editing={editingUserId === u.id}
                  onToggleEdit={() => setEditingUserId(editingUserId === u.id ? null : u.id)}
                  onSaved={() => { setEditingUserId(null); refresh(); }}
                  onError={(msg) => setActionError(msg)}
                  onDelete={() => removeUser(u.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      className="eyebrow"
      style={{
        textAlign: align,
        padding: "10px 14px",
        fontWeight: 600,
        borderBottom: "1px solid var(--border)",
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  className,
  align = "left",
}: {
  children: React.ReactNode;
  className?: string;
  align?: "left" | "right";
}) {
  return (
    <td style={{ padding: "10px 14px", textAlign: align }} className={className}>
      {children}
    </td>
  );
}

function fmt(iso: string, locale: "ru" | "en"): string {
  const d = new Date(iso);
  const bcp = localeBcp47(locale);
  const date = d.toLocaleDateString(bcp, { year: "numeric", month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(bcp, { hour: "2-digit", minute: "2-digit" });
  return `${date} · ${time}`;
}

function UserRowView({
  user,
  editing,
  onToggleEdit,
  onSaved,
  onError,
  onDelete,
}: {
  user: UserRow;
  editing: boolean;
  onToggleEdit: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
  onDelete: () => void;
}) {
  const { t, locale } = useT();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function changePassword() {
    if (!currentPassword || !newPassword) return;
    setBusy(true);
    try {
      await api.updateUser(user.id, { current_password: currentPassword, password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      onSaved();
    } catch (e) {
      onError(e instanceof Error ? e.message : t("admin.error.changePass"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleAdmin(next: boolean) {
    setBusy(true);
    try {
      await api.updateUser(user.id, { is_admin: next });
      onSaved();
    } catch (e) {
      onError(e instanceof Error ? e.message : t("admin.error.adminFlag"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr style={{ borderTop: "1px solid var(--border-soft)" }}>
        <Td><strong>{user.username}</strong></Td>
        <Td>
          {user.is_admin ? (
            <span className="badge badge-success">
              <span className="badge-dot" /> {t("admin.role.admin")}
            </span>
          ) : (
            <span className="badge badge-neutral">{t("admin.role.user")}</span>
          )}
        </Td>
        <Td className="muted">{fmt(user.created_at, locale)}</Td>
        <Td align="right">
          <button className="btn btn-ghost btn-sm" onClick={onToggleEdit}>
            {editing ? t("common.close") : t("common.edit")}
          </button>
        </Td>
      </tr>
      {editing && (
        <tr>
          <td colSpan={4} style={{ background: "var(--elevated)", padding: 14 }}>
            <div className="muted" style={{ marginBottom: 8, fontSize: "var(--text-small)" }}>
              {t("admin.changePassBody", {
                your: t("admin.changePassYour"),
                name: user.username,
              })}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                className="input"
                type="password"
                placeholder={t("admin.yourCurrentPass")}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                style={{ width: 200 }}
              />
              <input
                className="input"
                type="password"
                placeholder={t("admin.newPassFor", { name: user.username })}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{ width: 220 }}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={changePassword}
                disabled={busy || !currentPassword || !newPassword}
              >
                {t("admin.changePassword")}
              </button>
              {!user.is_admin && (
                <button className="btn btn-sm" onClick={() => toggleAdmin(true)} disabled={busy}>
                  {t("admin.promote")}
                </button>
              )}
              {user.is_admin && (
                <button className="btn btn-sm" onClick={() => toggleAdmin(false)} disabled={busy}>
                  {t("admin.demote")}
                </button>
              )}
              <button className="btn btn-danger btn-sm" onClick={onDelete} disabled={busy}>
                {t("admin.deleteUser")}
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
