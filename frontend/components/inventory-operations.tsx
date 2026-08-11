"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL, apiJson } from "@/lib/api";

type Option={id:string;name:string};
type Movement={id:string;created_at:string;movement_type:string;quantity:string;product:string;staff?:string;actor:string;notes?:string;reference_type?:string;reference_id?:string};

export function InventoryOperations({staff,products,movements,initialWarehouseProductId,view}:{staff:Option[];products:Option[];movements:Movement[];initialWarehouseProductId?:string;view:"receive"|"returns"|"adjustments"|"history"}) {
  const router=useRouter(); const [busy,setBusy]=useState(""); const [message,setMessage]=useState(""); const [error,setError]=useState("");
  async function submit(e:FormEvent<HTMLFormElement>,kind:"warehouse-in"|"returns"|"adjustments") {
    e.preventDefault(); setBusy(kind); setMessage(""); setError("");
    const form=e.currentTarget; const fd=new FormData(form);
    const payload:Record<string,unknown>={product_id:fd.get("product_id"),quantity:Number(fd.get("quantity")),idempotency_key:crypto.randomUUID()};
    if(kind==="warehouse-in") payload.note=fd.get("note")||null;
    if(kind==="returns"){payload.staff_id=fd.get("staff_id");payload.reason=fd.get("reason");}
    if(kind==="adjustments"){payload.staff_id=fd.get("staff_id")||null;payload.reason=fd.get("reason");}
    try { if(!confirm(`Post this ${kind.replace("-"," ")} movement? It cannot be edited later.`)) return; const res=await fetch(`${API_URL}/inventory/${kind}`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); await apiJson(res,"Movement could not be posted."); form.reset(); setMessage("Movement posted successfully."); router.refresh(); }
    catch(err){setError(err instanceof Error?err.message:"Movement could not be posted.");} finally {setBusy("");}
  }
  return <div className="space-y-8">
    {(message||error)&&<p role="alert" className={`rounded-xl p-3 text-sm ${error?"bg-red-50 text-red-700":"bg-emerald-50 text-emerald-800"}`}>{error||message}</p>}
    {view!=="history"&&<section className="mx-auto max-w-2xl"><p className="mb-4 text-sm text-slate-500">This creates an immutable ledger entry. Historical movements cannot be edited or removed.</p>
      {view==="receive"&&<MovementForm id="add-warehouse-stock" title="Receive Stock" submit={e=>submit(e,"warehouse-in")} busy={busy==="warehouse-in"} products={products} initialProductId={initialWarehouseProductId}><input name="note" placeholder="Optional note or reference" /></MovementForm>}
      {view==="returns"&&<MovementForm id="record-staff-return" title="Record Staff Return" submit={e=>submit(e,"returns")} busy={busy==="returns"} products={products} staff={staff}><textarea name="reason" required minLength={3} placeholder="Reason for return" /></MovementForm>}
      {view==="adjustments"&&<MovementForm id="adjustment" title="Stock Adjustment" submit={e=>submit(e,"adjustments")} busy={busy==="adjustments"} products={products} staff={staff} allowWarehouse><textarea name="reason" required minLength={3} placeholder="Required correction reason" /></MovementForm>}
    </section>}
    {view==="history"&&<section id="movement-history" className="scroll-mt-24"><div className="mb-3"><h2 className="font-semibold">Movement History</h2><p className="text-sm text-slate-500">Latest 100 ledger entries with actor and audit context.</p></div><div className="overflow-x-auto rounded-2xl border bg-white"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-leaf-50"><tr>{["Posted","Type","Product","Staff / location","Quantity","Actor","Reason / reference"].map(h=><th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody>{movements.length?movements.map(m=><tr key={m.id} className="border-t"><td className="px-4 py-3 whitespace-nowrap">{new Date(m.created_at).toLocaleString()}</td><td className="px-4 py-3 capitalize">{m.movement_type.replaceAll("_"," ")}</td><td className="px-4 py-3 font-medium">{m.product}</td><td className="px-4 py-3">{m.staff||"Warehouse"}</td><td className="px-4 py-3 font-bold">{m.quantity}</td><td className="px-4 py-3">{m.actor}</td><td className="max-w-xs px-4 py-3 text-slate-500">{m.notes||[m.reference_type,m.reference_id].filter(Boolean).join(" · ")||"—"}</td></tr>):<tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">No stock movements yet.</td></tr>}</tbody></table></div></section>}
  </div>;
}

function MovementForm({id,title,submit,busy,products,staff,allowWarehouse,initialProductId,children}:{id:string;title:string;submit:(e:FormEvent<HTMLFormElement>)=>void;busy:boolean;products:Option[];staff?:Option[];allowWarehouse?:boolean;initialProductId?:string;children:React.ReactNode}) { return <form id={id} onSubmit={submit} className="scroll-mt-24 space-y-3 rounded-2xl border bg-white p-5"><h3 className="font-semibold text-leaf-900">{title}</h3>{staff&&<select name="staff_id" required={!allowWarehouse}><option value="">{allowWarehouse?"Warehouse (no staff)":"Select staff"}</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}<select name="product_id" required defaultValue={initialProductId||""}><option value="">Select product</option>{products.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><input name="quantity" type="number" step="0.001" required placeholder={allowWarehouse?"Quantity (+ or −)":"Quantity"}/>{children}<button disabled={busy} className="w-full rounded-xl bg-leaf-700 px-4 py-2 font-semibold text-white disabled:opacity-50">{busy?"Posting…":"Confirm"}</button></form>;}
