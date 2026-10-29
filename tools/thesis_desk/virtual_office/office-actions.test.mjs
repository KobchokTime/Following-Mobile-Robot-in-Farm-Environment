import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import vm from "node:vm";

class Element {
  constructor() {
    this.children = [];
    this.handlers = new Map();
    this.classes = new Set();
    this.classList = {
      toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name),
    };
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute() {}
  addEventListener(name, callback) { this.handlers.set(name, callback); }
  querySelector() { return this.output; }
  click() { return this.handlers.get("click")?.(); }
}

test("rest keeps running meeting, desk work and chat agents at work until completion", async () => {
  const calls = [];
  const output = new Element();
  const side = new Element();
  const head = new Element();
  const rest = new Element();
  const seat = new Element();
  const meeting = new Element();
  const elements = { ".side": side, "#walk": rest, "#seat": seat, "#meeting": meeting };
  let actions = [];
  let busyAgents = [];
  let poll;
  const window = Object.fromEntries(["Rest", "Seat", "Meeting", "Idle"].map((kind) =>
    [`office${kind}`, (ids) => calls.push([kind, [...ids]])]));
  const context = {
    document: {
      head,
      querySelector: (selector) => elements[selector],
      createElement: () => { const element = new Element(); element.output = output; return element; },
    },
    window,
    sessionStorage: { getItem: () => null, setItem() {} },
    fetch: async () => ({ ok: true, json: async () => ({ actions, busyAgents }) }),
    setInterval: (callback) => { poll = callback; },
  };
  vm.runInNewContext(await readFile(new URL("./office-actions.js", import.meta.url), "utf8"), context);
  await new Promise((resolve) => setImmediate(resolve));
  await rest.click();
  assert.equal(rest.classes.has("active"), true);
  assert.equal(calls.filter(([kind]) => kind === "Rest").length, 12);
  calls.length = 0;

  const createdAt = new Date().toISOString();
  actions = [
    { id: "meeting-1", kind: "meeting", state: "running", createdAt,
      agents: ["natee", "fah", "dao"], summary: "planning" },
    { id: "seat-1", kind: "seat", state: "running", createdAt,
      agents: ["krit", "mew"], summary: "checking" },
  ];
  busyAgents = ["natee", "fah", "dao", "krit", "mew", "boss"];
  await poll();
  assert.deepEqual(calls.filter(([kind]) => kind === "Meeting"),
    [["Meeting", ["natee", "fah", "dao"]]]);
  assert.deepEqual(calls.filter(([kind]) => kind === "Seat").map(([, ids]) => ids),
    [["boss"], ["krit"], ["mew"]]);
  assert.equal(calls.some(([kind]) => kind === "Rest"), false);
  calls.length = 0;
  await poll();
  assert.equal(calls.length, 0, "polling must not interrupt a running action");

  actions = actions.map((action) => ({ ...action, state: "completed" }));
  busyAgents = [];
  await poll();
  assert.deepEqual(calls.filter(([kind]) => kind === "Rest").map(([, ids]) => ids),
    [["natee"], ["fah"], ["boss"], ["krit"], ["mew"], ["dao"]]);
});
