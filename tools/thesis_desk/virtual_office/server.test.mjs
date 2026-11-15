import assert from "node:assert/strict";
import { Readable } from "node:stream";
import { test } from "node:test";
import { classifyModelError, codexChildEnv, handleRequest, loggedInWithChatGPT, officeLogName, readMessage, teamDelegates } from "./server.mjs";

function response() {
  return {
    status: null, body: null,
    writeHead(status) { this.status = status; },
    end(body) { this.body = JSON.parse(body); },
  };
}

function request(body, headers = {}) {
  const req = Readable.from([body]);
  req.headers = { "content-type": "application/json", ...headers };
  req.method = "POST";
  req.url = "/api/agents/mew/messages";
  return req;
}

test("rejects JSON null and non-string fields without throwing", async () => {
  for (const body of ["null", "[]", "42", '{"message":{},"session":"12345678"}']) {
    const res = response();
    assert.equal(await readMessage(request(body), res), null);
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
  }
});

test("accepts a valid chat message", async () => {
  const res = response();
  const body = JSON.stringify({ message: "  hello  ", session: "session-123" });
  assert.deepEqual(await readMessage(request(body), res),
    { message: "hello", session: "session-123" });
  assert.equal(res.status, null);
});

test("chat parser rejects text/plain even when the body is JSON", async () => {
  const res = response();
  const req = request('{"message":"hello","session":"session-123"}',
    { "content-type": "text/plain" });
  assert.equal(await readMessage(req, res), null);
  assert.equal(res.status, 415);
});

test("local server rejects foreign Host, foreign Origin and non-JSON POST before chat", async () => {
  const localHost = `127.0.0.1:${process.env.PORT || 8765}`;
  const body = '{"message":"hello","session":"session-123"}';
  for (const [headers, status] of [
    [{ host: `attacker.example:${process.env.PORT || 8765}` }, 403],
    [{ host: localHost, origin: "https://evil.example" }, 403],
    [{ host: localHost, origin: `http://localhost:${process.env.PORT || 8765}` }, 403],
    [{ host: localHost, "content-type": "text/plain" }, 415],
  ]) {
    const res = response();
    await handleRequest(request(body, headers), res);
    assert.equal(res.status, status);
  }
  const res = response();
  const valid = request(body, { host: localHost });
  valid.method = "GET";
  valid.url = "/api/agents";
  await handleRequest(valid, res);
  assert.equal(res.status, 200);
  const rebinding = request(body, { host: `attacker.example:${process.env.PORT || 8765}` });
  rebinding.method = "GET";
  rebinding.url = "/api/agents";
  const denied = response();
  await handleRequest(rebinding, denied);
  assert.equal(denied.status, 403);
  const localhost = request(body, { host: `localhost:${process.env.PORT || 8765}`,
    origin: `http://localhost:${process.env.PORT || 8765}`,
    "content-type": "application/json; charset=utf-8" });
  localhost.method = "GET";
  localhost.url = "/api/agents";
  const allowed = response();
  await handleRequest(localhost, allowed);
  assert.equal(allowed.status, 200);
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
  assert.equal(classifyModelError({ status: 429 }).status, 429);
  const other = classifyModelError(new Error("private prompt and local path"));
  assert.deepEqual(other, { status: 502, error: "agent ตอบกลับไม่ได้ โปรดลองอีกครั้ง" });
});

test("Team Lead stops before summary when any specialist hits 429", () => {
  const limited = new Error("last status: 429 Too Many Requests");
  const answered = { id: "mew", answer: "ตอบแล้ว" };
  for (const results of [
    [{ status: "rejected", reason: limited }],
    [{ status: "fulfilled", value: answered }, { status: "rejected", reason: limited }],
  ]) {
    assert.throws(() => teamDelegates(results), (error) => error === limited);
  }
  assert.deepEqual(teamDelegates([
    { status: "rejected", reason: new Error("temporary failure") },
    { status: "fulfilled", value: answered },
  ]), [answered]);
});

test("raw Office log links cannot escape their recorded file names", () => {
  assert.equal(officeLogName("4ef21a55-ea50-4e11-90e7-42b0248aea41-krit.txt"), true);
  for (const name of ["../secret", "..\\secret", "meeting.txt", "4ef21a55-ea50-4e11-90e7-42b0248aea41-krit.txt/../secret"])
    assert.equal(officeLogName(name), false);
});
