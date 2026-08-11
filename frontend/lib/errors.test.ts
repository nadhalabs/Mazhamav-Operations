import assert from "node:assert/strict";import test from "node:test";import{apiJson}from"./api.ts";
test("non-JSON API failures produce a business-facing fallback",async()=>{await assert.rejects(apiJson(new Response("proxy error",{status:502,headers:{"content-type":"text/html"}}),"Service unavailable"),/Service unavailable/)});
test("authentication failures have a useful session message",async()=>{await assert.rejects(apiJson(new Response(null,{status:401}),"Failed"),/session expired/)});
