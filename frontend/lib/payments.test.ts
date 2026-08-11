import test from "node:test";
import assert from "node:assert/strict";
import { PAYMENT_METHODS, paymentReceiptPath } from "./payments.ts";

test("pending payment collection uses the existing sale receipt endpoint", () => {
  assert.equal(paymentReceiptPath("sale-id"), "/payments/sales/sale-id/received");
});

test("collection offers every backend-supported payment method", () => {
  assert.deepEqual(PAYMENT_METHODS, ["cash", "upi", "bank_transfer", "credit", "other"]);
});
