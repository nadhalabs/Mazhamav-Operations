import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { IssueStockForm } from "@/components/issue-stock-form";
import { getCurrentUser, serverGet } from "@/lib/api";
type Options = { staff: { id: string; name: string }[]; products: { id: string; name: string; sku: string; unit_name: string }[] };
type Warehouse={product_id:string;current_balance:string};type StaffStock={staff_id:string;product_id:string;current_balance:string};
export default async function IssuePage() { const cookie = (await cookies()).toString(); const user = await getCurrentUser(cookie); if (!user) redirect("/login"); if (user.role === "staff") redirect("/staff"); const [options,warehouseRows,staffRows]=await Promise.all([serverGet<Options>("/inventory/options", cookie),serverGet<Warehouse[]>("/inventory/warehouse",cookie),serverGet<StaffStock[]>("/inventory/staff-overview",cookie)]);const warehouse=Object.fromEntries(warehouseRows.map(r=>[r.product_id,r.current_balance]));const staffStock=Object.fromEntries(staffRows.map(r=>[`${r.staff_id}:${r.product_id}`,r.current_balance]));return <AppShell user={user} title="Issue stock"><p className="mb-6 max-w-2xl text-sm leading-6 text-slate-500">Issue available warehouse stock to a staff member. Confirmation creates a permanent ledger entry and cannot be edited.</p><IssueStockForm {...options} warehouse={warehouse} staffStock={staffStock}/></AppShell>; }
