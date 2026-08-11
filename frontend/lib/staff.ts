export type StaffFilterRow = { full_name: string; phone: string; role: "staff" | "manager"; active: boolean };

export function filterStaffRows<T extends StaffFilterRow>(rows: T[], query: string, role: string, status: string): T[] {
  const term = query.trim().toLowerCase();
  return rows.filter(row =>
    (!term || `${row.full_name} ${row.phone}`.toLowerCase().includes(term)) &&
    (!role || row.role === role) &&
    (!status || row.active === (status === "active"))
  );
}
