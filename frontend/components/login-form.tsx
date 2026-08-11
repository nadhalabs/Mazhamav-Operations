"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL, CurrentUser } from "@/lib/api";

export function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API_URL}/auth/login`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone: data.get("phone"), password: data.get("password") }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? "Unable to sign in");
      const user = body as CurrentUser;
      router.replace(user.role === "staff" ? "/staff" : "/admin"); router.refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to sign in"); } finally { setLoading(false); }
  }
  return <form onSubmit={submit} className="space-y-5">
    <div><label className="mb-2 block text-sm font-medium" htmlFor="phone">Phone number</label><input id="phone" name="phone" autoComplete="tel" required /></div>
    <div><label className="mb-2 block text-sm font-medium" htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" minLength={8} required /></div>
    {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
    <button disabled={loading} className="w-full rounded-xl bg-leaf-700 px-4 py-3 font-semibold text-white hover:bg-leaf-900">{loading ? "Signing in…" : "Sign in"}</button>
  </form>;
}

