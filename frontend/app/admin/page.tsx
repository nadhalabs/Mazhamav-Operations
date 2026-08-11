import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { OwnerDashboard } from "@/components/owner-dashboard";
import { StaffProfileShortcuts } from "@/components/staff-profile-shortcuts";
import { getCurrentUser, serverGet } from "@/lib/api";
import Link from "next/link";

export default async function AdminPage({searchParams}:{searchParams:Promise<Record<string,string>>}) {
  const cookie=(await cookies()).toString(); const user=await getCurrentUser(cookie);
  if(!user)redirect("/login"); if(user.role==="staff")redirect("/staff"); if(user.role==="manager")redirect("/admin/inventory");
  const params=await searchParams; const period=params.period||"last_30_days"; const query=new URLSearchParams({period});
  if(params.date_from)query.set("date_from",params.date_from); if(params.date_to)query.set("date_to",params.date_to);
  const data=await serverGet<any>(`/dashboard/owner?${query}`,cookie);
  return <AppShell user={user} title="Owner dashboard"><div className="mb-5 flex flex-wrap gap-2">{[["Manage products","/admin/products"],["Warehouse inventory","/admin/inventory"],["Pending payments","/admin/sales?payment_status=pending"],["Stock requests","/admin/stock-requests"],["Retailers","/admin/retailers"],["Download reports","/admin/reports"]].map(([label,href])=><Link key={href} href={href} className="rounded-xl border bg-white px-3 py-2 text-sm font-semibold text-leaf-700 hover:border-leaf-600">{label}</Link>)}</div><StaffProfileShortcuts rows={data.staff_performance}/><OwnerDashboard data={data}/></AppShell>;
}
