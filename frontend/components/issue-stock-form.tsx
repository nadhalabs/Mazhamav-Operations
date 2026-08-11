"use client";
import { FormEvent, useRef, useState } from "react";
import { API_URL, apiJson } from "@/lib/api";

type Option = { id: string; name: string; sku?: string; unit_name?: string };

export function IssueStockForm({ staff, products, warehouse, staffStock }: { staff: Option[]; products: Option[]; warehouse:Record<string,string>;staffStock:Record<string,string> }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [state, setState] = useState<{ loading: boolean; error?: string; success?: string }>({ loading: false });
  const [staffId,setStaffId]=useState(""); const [productId,setProductId]=useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("Issue this stock? This posts an immutable ledger movement.")) return;
    setState({ loading: true });
    const data = new FormData(event.currentTarget);
    const body = { staff_id: data.get("staff_id"), product_id: data.get("product_id"), quantity: data.get("quantity"), note: data.get("note") || null, idempotency_key: crypto.randomUUID() };
    try {
      const response = await fetch(`${API_URL}/inventory/issues`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      await apiJson(response, "Stock could not be issued");
      formRef.current?.reset(); setStaffId(""); setProductId(""); setState({ loading: false, success: "Stock issued and recorded in the ledger." });
    } catch (error) { setState({ loading: false, error: error instanceof Error ? error.message : "Stock could not be issued" }); }
  }
  return <form ref={formRef} onSubmit={submit} className="max-w-2xl space-y-5 rounded-2xl border bg-white p-6 shadow-sm">
    <div><label className="mb-2 block text-sm font-medium">Staff member</label><select name="staff_id" value={staffId} onChange={e=>setStaffId(e.target.value)} required className="w-full rounded-xl border px-4 py-3"><option value="">Select staff</option>{staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
    <div><label className="mb-2 block text-sm font-medium">Product</label><select name="product_id" value={productId} onChange={e=>setProductId(e.target.value)} required className="w-full rounded-xl border px-4 py-3"><option value="">Select product</option>{products.map(p => <option key={p.id} value={p.id}>{p.name} · {p.sku}</option>)}</select></div>
    {productId&&<div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-leaf-50 p-3"><p className="text-xs text-slate-500">Warehouse available</p><p className="text-xl font-bold text-leaf-900">{warehouse[productId]??"0"}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Staff current balance</p><p className="text-xl font-bold">{staffId?staffStock[`${staffId}:${productId}`]??"0":"Select staff"}</p></div></div>}
    <div><label className="mb-2 block text-sm font-medium">Quantity</label><input name="quantity" type="number" min="0.001" step="0.001" required /></div>
    <div><label className="mb-2 block text-sm font-medium">Note <span className="font-normal text-slate-400">(optional)</span></label><textarea name="note" rows={3} maxLength={1000} className="w-full rounded-xl border px-4 py-3" /></div>
    {state.error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{state.error}</p>}{state.success && <p role="status" className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{state.success}</p>}
    <button disabled={state.loading || !staff.length || !products.length} className="rounded-xl bg-leaf-700 px-5 py-3 font-semibold text-white hover:bg-leaf-900">{state.loading ? "Posting…" : "Confirm stock issue"}</button>
  </form>;
}
