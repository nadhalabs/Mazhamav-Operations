"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_URL, CurrentUser } from "@/lib/api";

const navClass = "rounded-lg px-3 py-2 hover:bg-leaf-50";

export function AppShell({ user, title, children }: { user: CurrentUser; title: string; children: React.ReactNode }) {
  const router = useRouter();
  async function logout() {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
    router.replace("/login"); router.refresh();
  }
  const home = user.role === "staff" ? "/staff" : "/admin";
  return <div className="min-h-screen"><header className="border-b border-leaf-900/10 bg-white"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4"><div><Link href={home} className="font-bold text-leaf-900">Mazha Mav</Link><p className="text-xs capitalize text-slate-500">{user.role} workspace</p></div><nav className="flex flex-wrap items-center gap-1 text-sm">{user.role === "staff" ? <><Link className={navClass} href="/staff/record-sale">Record Sale</Link><Link className={navClass} href="/staff/my-stock">My Stock</Link><Link className={navClass} href="/staff/request-stock">Request Stock</Link><Link className={navClass} href="/staff/history">History</Link></> : <>{user.role === "owner" && <><Link className={navClass} href="/admin">Dashboard</Link><Link className={navClass} href="/admin/staff">Staff</Link></>}<Link className={navClass} href="/admin/inventory">Inventory</Link><Link className={navClass} href="/admin/sales">Sales</Link><Link className={navClass} href="/admin/retailers">Retailers</Link><Link className={navClass} href="/admin/stock-requests">Stock Requests</Link>{user.role === "owner" && <Link className={navClass} href="/admin/settings/payments">Settings</Link>}<Link className="rounded-lg bg-leaf-700 px-3 py-2 text-white" href="/admin/inventory/issue">Issue Stock</Link></>}<button onClick={logout} className="rounded-lg border px-3 py-2 hover:bg-slate-50">Sign out</button></nav></div></header><main className="mx-auto max-w-6xl p-5 sm:py-10"><h1 className="text-2xl font-bold tracking-tight">{title}</h1><p className="mt-1 text-sm text-slate-500">Welcome, {user.full_name}</p><div className="mt-8">{children}</div></main></div>;
}
