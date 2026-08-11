import assert from "node:assert/strict";
import test from "node:test";
import { filterStaffRows } from "./staff.ts";

const rows = [
  { full_name: "Anu Sales", phone: "9000000010", role: "staff" as const, active: true },
  { full_name: "Binu Manager", phone: "9000000020", role: "manager" as const, active: false },
];

test("staff directory searches names and phone numbers", () => {
  assert.equal(filterStaffRows(rows, "anu", "", "").length, 1);
  assert.equal(filterStaffRows(rows, "0020", "", "")[0].full_name, "Binu Manager");
});

test("staff directory applies role and status filters together", () => {
  assert.deepEqual(filterStaffRows(rows, "", "manager", "disabled").map(row => row.full_name), ["Binu Manager"]);
  assert.deepEqual(filterStaffRows(rows, "", "staff", "active").map(row => row.full_name), ["Anu Sales"]);
});
