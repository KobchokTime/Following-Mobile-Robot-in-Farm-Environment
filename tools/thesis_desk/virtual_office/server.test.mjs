import assert from "node:assert/strict";
import { Readable } from "node:stream";
import { test } from "node:test";
import { classifyModelError, codexChildEnv, loggedInWithChatGPT, readMessage } from "./server.mjs";

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

test("Office chat requires ChatGPT login and strips paid API settings", () => {
  assert.equal(loggedInWithChatGPT({ status: 0, stdout: "Logged in using ChatGPT" }), true);
  assert.equal(loggedInWithChatGPT({ status: 0, stdout: "Logged in using API key" }), false);
  assert.equal(loggedInWithChatGPT({ status: 1, stdout: "Logged in using ChatGPT" }), false);
  const child = codexChildEnv({ PATH: "example", OPENAI_API_KEY: "secret",
    CODEX_API_KEY: "secret", OPENAI_ADMIN_KEY: "secret", OPENAI_BASE_URL: "https://paid.example" });
  assert.deepEqual(child, { PATH: "example" });
});

test("rate-limit errors are safe to show and other CLI stderr stays private", () => {
  const limited = classifyModelError(new Error("private prompt\nlast status: 429 Too Many Requests"));
  assert.deepEqual(limited, { status: 429,
    error: "Codex จำกัดคำขอชั่วคราว (429) โปรดลองอีกครั้งภายหลัง" });
  const other = classifyModelError(new Error("private prompt and local path"));
  assert.deepEqual(other, { status: 502, error: "agent ตอบกลับไม่ได้ โปรดลองอีกครั้ง" });
});
