"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/app/providers";
import { t } from "@/lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

export default function LoginPage() {
  const { locale } = useI18n();
  const router = useRouter();
  const [tenantId, setTenantId] = useState("default");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(path: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenantId, username, password, locale })
      });
      const data = await res.json();
      if (!res.ok) {
        setError((data.detail ?? "Login failed").toString());
        return;
      }
      localStorage.setItem("zodel_token", data.token);
      localStorage.setItem("zodel_user", JSON.stringify(data.user));
      router.push("/chat");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-md px-6 py-10">
        <div className="text-2xl font-semibold">{t(locale, "app.title")}</div>
        <div className="mt-2 text-sm text-neutral-400">Auth (minimal, for SaaS evolution)</div>

        <div className="mt-6 space-y-3 rounded-xl border border-neutral-800 bg-neutral-950 p-4">
          <div>
            <label className="text-xs text-neutral-400">Tenant</label>
            <input
              className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-neutral-400">Username</label>
            <input
              className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-neutral-400">Password</label>
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error ? <div className="text-sm text-red-300">{error}</div> : null}

          <div className="flex gap-2 pt-2">
            <button
              className="flex-1 rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
              onClick={() => void call("/api/auth/login")}
              disabled={busy || !username.trim() || password.length < 6}
            >
              Login
            </button>
            <button
              className="flex-1 rounded-md border border-neutral-800 px-3 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
              onClick={() => void call("/api/auth/signup")}
              disabled={busy || !username.trim() || password.length < 6}
            >
              Sign up
            </button>
          </div>
        </div>

        <div className="mt-4 text-xs text-neutral-500">
          Token is stored in localStorage as <code>zodel_token</code>.
        </div>
      </div>
    </div>
  );
}

