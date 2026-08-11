import assert from "node:assert/strict";
import test from "node:test";
import { serverGetOptional } from "./api.ts";

test("optional server reads convert a missing payment configuration into an empty state", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 404 }));
  assert.equal(await serverGetOptional("/payments/qr-context", "access_token=test"), null);
});

test("optional server reads still surface unexpected API failures", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 500 }));
  await assert.rejects(serverGetOptional("/payments/qr-context", "access_token=test"), /API request failed: 500/);
});
