import assert from "node:assert/strict";
import { Readable } from "node:stream";
import { test } from "node:test";
import { readMessage } from "./server.mjs";

function response() {
  return {
    status: null, body: null,
    writeHead(status) { this.status = status; },
    end(body) { this.body = JSON.parse(body); },
  };
}

test("rejects JSON null and non-string fields without throwing", async () => {
  for (const body of ["null", "[]", "42", '{"message":{},"session":"12345678"}']) {
    const res = response();
    assert.equal(await readMessage(Readable.from([body]), res), null);
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
  }
});

test("accepts a valid chat message", async () => {
  const res = response();
  const body = JSON.stringify({ message: "  hello  ", session: "session-123" });
  assert.deepEqual(await readMessage(Readable.from([body]), res),
    { message: "hello", session: "session-123" });
  assert.equal(res.status, null);
});
