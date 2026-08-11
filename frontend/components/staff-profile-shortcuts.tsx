import Link from "next/link";

export function StaffProfileShortcuts({ rows }: { rows: { staff_id: string; staff: string; sales_value: string; current_stock: string }[] }) {
  if (!rows.length) return null;
  return <section className="mb-8 rounded-2xl border bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">Staff performance profiles</h2><p className="text-sm text-slate-500">Open the underlying staff detail for the dashboard’s current performance data.</p></div><Link href="/admin/staff" className="text-sm font-semibold text-leaf-700">Manage staff</Link></div><div className="mt-4 flex flex-wrap gap-2">{rows.map(row=><Link key={row.staff_id} href={`/admin/staff/${row.staff_id}`} className="rounded-xl border px-3 py-2 text-sm hover:border-leaf-600 hover:bg-leaf-50"><b>{row.staff}</b><span className="ml-2 text-slate-400">₹{Number(row.sales_value).toLocaleString("en-IN")} · stock {Number(row.current_stock).toLocaleString("en-IN")}</span></Link>)}</div></section>;
}
