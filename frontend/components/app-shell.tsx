"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { API_URL, CurrentUser } from "@/lib/api";

type NavItem = { href: string; label: string; ownerOnly?: boolean };

const adminNav: NavItem[] = [
  { href: "/admin", label: "Dashboard", ownerOnly: true },
  { href: "/admin/staff", label: "Staff", ownerOnly: true },
  { href: "/admin/products", label: "Products", ownerOnly: true },
  { href: "/admin/inventory", label: "Inventory" },
  { href: "/admin/sales", label: "Sales" },
  { href: "/admin/retailers", label: "Retailers" },
  { href: "/admin/stock-requests", label: "Stock Requests" },
  { href: "/admin/reports", label: "Reports", ownerOnly: true },
  { href: "/admin/settings/payments", label: "Payment Settings", ownerOnly: true },
  { href: "/admin/settings", label: "Settings", ownerOnly: true },
];

const staffNav: NavItem[] = [
  { href: "/staff", label: "Home" },
  { href: "/staff/record-sale", label: "Record Sale" },
  { href: "/staff/my-stock", label: "My Stock" },
  { href: "/staff/request-stock", label: "Request Stock" },
  { href: "/staff/payment-qr", label: "Payment QR" },
  { href: "/staff/history", label: "History" },
];

export function AppShell({ user, title, children }: { user: CurrentUser; title: string; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const home = user.role === "staff" ? "/staff" : "/admin";
  const nav = (user.role === "staff" ? staffNav : adminNav).filter(item => !item.ownerOnly || user.role === "owner");

  async function logout() {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
    router.replace("/login");
    router.refresh();
  }

  const links = nav.map(item => {
    const active = pathname === item.href || (item.href !== home && pathname.startsWith(`${item.href}/`));
    return <Link key={item.href} href={item.href} className={`rounded-lg px-3 py-2 text-sm transition ${active ? "bg-leaf-100 font-semibold text-leaf-900" : "text-slate-600 hover:bg-leaf-50 hover:text-leaf-900"}`}>{item.label}</Link>;
  });

  return <div className="min-h-screen bg-slate-50/60">
    <header className="sticky top-0 z-40 border-b border-leaf-900/10 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="shrink-0"><Link href={home} className="font-bold text-leaf-900">Mazha Mav</Link><p className="text-xs capitalize text-slate-500">{user.role} workspace</p></div>
        <nav className="hidden flex-wrap items-center justify-end gap-1 xl:flex">{links}<button onClick={logout} className="rounded-lg border px-3 py-2 text-sm hover:bg-slate-50">Sign out</button></nav>
        <details className="relative xl:hidden"><summary className="cursor-pointer list-none rounded-lg border px-3 py-2 text-sm font-semibold">Menu</summary><div className="absolute right-0 mt-2 flex w-64 flex-col rounded-2xl border bg-white p-2 shadow-xl">{links}<button onClick={logout} className="mt-1 rounded-lg border px-3 py-2 text-left text-sm text-red-700">Sign out</button></div></details>
      </div>
    </header>
    <main className="mx-auto max-w-7xl p-4 sm:px-6 sm:py-8"><div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-bold tracking-tight text-slate-950">{title}</h1><p className="mt-1 text-sm text-slate-500">Welcome, {user.full_name}</p></div>{user.role !== "staff" && <Link href="/admin/inventory/issue" className="rounded-xl bg-leaf-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-leaf-800">Issue stock</Link>}</div><div className="mt-6">{children}</div></main>
  </div>;
}
