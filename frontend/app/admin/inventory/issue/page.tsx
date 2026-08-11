import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { IssueStockForm } from "@/components/issue-stock-form";
import { getCurrentUser, serverGet } from "@/lib/api";
type Options = { staff: { id: string; name: string }[]; products: { id: string; name: string; sku: string; unit_name: string }[] };
export default async function IssuePage() { const cookie = (await cookies()).toString(); const user = await getCurrentUser(cookie); if (!user) redirect("/login"); if (user.role === "staff") redirect("/staff"); const options = await serverGet<Options>("/inventory/options", cookie); return <AppShell user={user} title="Issue stock"><p className="mb-6 max-w-2xl text-sm leading-6 text-slate-500">Issue available warehouse stock to a staff member. Confirmation creates a permanent ledger entry and cannot be edited.</p><IssueStockForm {...options} /></AppShell>; }
