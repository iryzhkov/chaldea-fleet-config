// Contract tests for the rendered OpenCode Jocasta plugin. tests/test_webmcp_opencode.py
// renders it into a scratch HOME and runs this file. Every helper process here is a
// fake; the real helper is never spawned.
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { copyFile, mkdir, readFile } from "node:fs/promises";
import { realpathSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const pluginPath = process.env.WEBMCP_JOCASTA_PLUGIN;
const home = process.env.WEBMCP_JOCASTA_HOME;
const host = process.env.WEBMCP_JOCASTA_HOST;
const uid = Number(process.env.WEBMCP_JOCASTA_UID);
assert.ok(pluginPath && home && host && Number.isSafeInteger(uid), "rendered plugin inputs are required");
assert.equal(process.env.HOME, home, "tests run only in the scratch HOME the plugin was rendered for");
assert.equal(pluginPath, path.join(home, ".config/opencode/plugins/webmcp-jocasta.js"));

const HELPER = "/usr/local/libexec/webmcp-interactive-headers";
const URL = "https://jocasta.mcp.ryzhkov.dev/mcp";
const source = await readFile(pluginPath, "utf8");
const plugin = await import(pathToFileURL(pluginPath).href);
const { createPlugin, parseHelperOutput } = plugin;

// Any console use would be a redaction failure; the plugin has no logging.
const consoleCalls = [];
for (const method of ["log", "info", "warn", "error", "debug", "trace"]) {
  const original = console[method];
  console[method] = (...args) => {
    consoleCalls.push(method);
    original.apply(console, args);
  };
}

const b64 = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
const jwt = (expMs, tag = "a") => b64({ alg: "RS256", typ: "JWT" }) + "."
  + b64({ exp: Math.floor(expMs / 1000), sub: "fixture-" + tag }) + "."
  + Buffer.from("signature-" + tag).toString("base64url");
const output = (token) => JSON.stringify({ Authorization: "Bearer " + token }) + "\n";
const flush = async () => {
  for (let i = 0; i < 20; i++) await new Promise((resolve) => setImmediate(resolve));
};

class FakeChild extends EventEmitter {
  constructor(pid) {
    super();
    this.stdout = new EventEmitter();
    this.pid = pid;
    this.signals = [];
    this.ended = false;
    this.onSignal = (signal) => this.end(null, signal);
  }
  kill(signal) {
    this.signals.push(signal);
    queueMicrotask(() => this.onSignal(signal));
    return true;
  }
  reply(text, code = 0) {
    if (text) this.stdout.emit("data", Buffer.from(text));
    this.end(code, null);
  }
  end(code, signal) {
    if (this.ended) return;
    this.ended = true;
    this.emit("close", code, signal);
  }
}

function harness(overrides = {}) {
  const clock = { now: 1_900_000_000_000 };
  const timers = new Map();
  let nextTimer = 1;
  const spawns = [];
  const children = [];
  const runtime = {
    now: () => clock.now,
    setTimeout: (run, delay) => {
      const handle = { id: nextTimer++, at: clock.now + delay, run, unrefed: false,
        unref() { this.unrefed = true; } };
      timers.set(handle.id, handle);
      return handle;
    },
    clearTimeout: (handle) => { if (handle) timers.delete(handle.id); },
    getuid: () => uid,
    realpath: (target) => realpathSync(target),
    env: { HOME: home },
    modulePath: pluginPath,
    spawn: (...args) => {
      spawns.push(structuredClone(args));
      if (overrides.spawnThrows) throw new Error("spawn failed: " + HELPER);
      const child = new FakeChild(5000 + children.length);
      children.push(child);
      return child;
    },
    ...overrides.runtime,
  };
  return {
    runtime, clock, timers, spawns, children,
    get child() { return children.at(-1); },
    async advance(ms) {
      const end = clock.now + ms;
      for (;;) {
        await flush();
        const due = [...timers.values()].filter((t) => t.at <= end)
          .sort((a, b) => a.at - b.at || a.id - b.id)[0];
        if (!due) break;
        timers.delete(due.id);
        clock.now = Math.max(clock.now, due.at);
        due.run();
      }
      clock.now = end;
      await flush();
    },
  };
}

function context(initial = {}, { version = "2.1.4", batched = false } = {}) {
  const base = new Map(Object.entries(structuredClone(initial)));
  const transforms = [];
  const disposed = [];
  let servers = new Map();
  let pending = batched;
  const editor = {
    list: () => [...servers],
    get: (name) => servers.get(name),
    set: (name, config) => { servers.set(name, structuredClone(config)); },
    update: (name, update) => { const current = servers.get(name); if (current) update(current); },
    remove: (name) => { servers.delete(name); },
  };
  const ctx = {
    reloads: 0,
    app: version === null ? undefined : { name: "opencode", version, channel: "latest" },
    location: { directory: home },
    mcp: {
      transform: async (run) => {
        const entry = { run };
        transforms.push(entry);
        if (!pending) rebuild();
        return { dispose: async () => {
          transforms.splice(transforms.indexOf(entry), 1);
          disposed.push(entry);
          rebuild();
        } };
      },
      reload: async () => {
        ctx.reloads++;
        rebuild();
      },
    },
  };
  function rebuild() {
    servers = new Map([...base].map(([name, config]) => [name, structuredClone(config)]));
    for (const entry of transforms) entry.run(editor);
  }
  return {
    ctx, base, transforms, disposed,
    servers: () => servers,
    endBatch() { pending = false; rebuild(); },
    rebuild,
  };
}

const unrelated = { type: "remote", url: "https://other.example/mcp", headers: { "X-Other": "keep" } };
const huyang = { type: "local", command: ["/home/fixture/.local/share/huyang/bin/huyang", "mcp"] };
const expected = (token) => ({ type: "remote", url: URL, oauth: false, headers: { Authorization: "Bearer " + token } });

async function started(options = {}) {
  const h = harness(options);
  const c = context(options.initial ?? { unrelated, huyang }, options.context);
  const cleanup = await createPlugin(h.runtime).setup(c.ctx);
  return { h, c, cleanup };
}

async function withToken(options = {}) {
  const s = await started(options);
  await s.h.advance(0);
  const token = jwt(s.h.clock.now + 300_000, "a");
  s.h.child.reply(output(token));
  await flush();
  return { ...s, token };
}

test("rendered module exposes the fixed default definition and production constants", () => {
  assert.equal(plugin.default.id, "fleet.webmcp-jocasta");
  assert.equal(typeof plugin.default.setup, "function");
  assert.ok(source.startsWith("// fleet-managed: webmcp-jocasta/v1\n"));
  assert.ok(source.includes(`const HELPER = "${HELPER}";\n`));
  assert.ok(source.includes(`const URL = "${URL}";\n`));
  assert.ok(source.includes(`const DECLARATION = Object.freeze(${JSON.stringify({ host, uid, home }).replaceAll(",", ", ").replaceAll(":", ": ")});\n`));
  assert.ok(!/console\.|process\.env\.[A-Z]|writeFile|appendFile|fetch\(/.test(source));
  assert.ok(!source.includes("{%") && !source.includes("{{"));
});

test("init ordering: transform first, no helper until it has observed config, then exact spawn", async () => {
  const h = harness();
  const c = context({ unrelated }, { batched: true });
  await createPlugin(h.runtime).setup(c.ctx);
  assert.equal(c.transforms.length, 1);
  await h.advance(1000);
  assert.equal(h.spawns.length, 0, "boot batch not applied yet");
  c.endBatch();
  assert.equal(c.servers().has("jocasta"), false, "no entry before a token exists");
  await h.advance(250);
  assert.equal(h.spawns.length, 1);
  assert.deepEqual(h.spawns[0], [HELPER, ["jocasta", host],
    { cwd: "/", env: { PATH: "/usr/bin:/bin" }, shell: false, stdio: ["ignore", "pipe", "ignore"] }]);
  const token = jwt(h.clock.now + 300_000);
  const reloads = c.ctx.reloads;
  h.child.reply(output(token));
  await flush();
  assert.equal(c.ctx.reloads, reloads + 1);
  assert.deepEqual(c.servers().get("jocasta"), expected(token));
  assert.deepEqual(c.servers().get("unrelated"), unrelated);
  assert.ok([...h.timers.values()].every((t) => t.unrefed), "owned timers are unref'd");
});

test("refresh replaces the token at half its bounded life and preserves neighbors", async () => {
  const { h, c, token } = await withToken();
  assert.deepEqual(c.servers().get("jocasta"), expected(token));
  await h.advance(144_000);
  assert.equal(h.spawns.length, 1);
  await h.advance(1_000);
  assert.equal(h.spawns.length, 2);
  const next = jwt(h.clock.now + 300_000, "b");
  h.child.reply(output(next));
  await flush();
  assert.deepEqual(c.servers().get("jocasta"), expected(next));
  assert.deepEqual(c.servers().get("unrelated"), unrelated);
  assert.deepEqual(c.servers().get("huyang"), huyang);
  assert.ok(!JSON.stringify([...c.servers()].filter(([n]) => n !== "jocasta")).includes("Bearer"));
});

test("a longer helper claim is clamped to the 300s contract", () => {
  const now = 1_900_000_000_000;
  const parsed = parseHelperOutput(Buffer.from(output(jwt(now + 3_600_000))), now);
  assert.equal(parsed.deadline, now + 290_000);
});

test("failure keeps a valid token only until its deadline, then removes it and recovers", async () => {
  const { h, c, token } = await withToken();
  await h.advance(145_000);
  h.child.reply("", 1);
  await flush();
  assert.deepEqual(c.servers().get("jocasta"), expected(token), "still inside its bounded validity");
  for (let i = 0; i < 9; i++) {
    await h.advance(15_000);
    h.child.reply("", 1);
    await flush();
  }
  assert.equal(h.spawns.length, 11);
  // The tenth retry is clamped to the deadline: issued + 290s.
  await h.advance(10_000);
  assert.equal(c.servers().has("jocasta"), false, "removed at its deadline");
  assert.deepEqual(c.servers().get("unrelated"), unrelated);
  h.child.reply("", 1);
  await flush();
  await h.advance(15_000);
  const next = jwt(h.clock.now + 300_000, "c");
  h.child.reply(output(next));
  await flush();
  assert.deepEqual(c.servers().get("jocasta"), expected(next));
});

test("the transform withholds an expired token even if no timer ran", async () => {
  const { h, c } = await withToken();
  h.timers.clear();
  h.clock.now += 290_000;
  c.rebuild();
  assert.equal(c.servers().has("jocasta"), false);
});

const malformed = [
  ["empty", () => ""],
  ["no newline", (t) => output(t).trimEnd()],
  ["two lines", (t) => output(t) + output(t)],
  ["extra key", (t) => JSON.stringify({ Authorization: "Bearer " + t, X: "y" }) + "\n"],
  ["spaced JSON", (t) => JSON.stringify({ Authorization: "Bearer " + t }, null, 1) + "\n"],
  ["not bearer", (t) => JSON.stringify({ Authorization: "Basic " + t }) + "\n"],
  ["two segments", (t) => output(t.split(".").slice(0, 2).join("."))],
  ["bad characters", (t) => output(t + "=")],
  ["payload not JSON", (t) => output([t.split(".")[0], "bm90LWpzb24", "c2ln"].join("."))],
  ["exp missing", () => output([b64({}), b64({ sub: "x" }), "c2ln"].join("."))],
  ["exp string", () => output([b64({}), b64({ exp: "9999999999" }), "c2ln"].join("."))],
  ["exp too soon", () => output(jwt(1_900_000_000_000 + 20_000))],
  ["exp past", () => output(jwt(1_900_000_000_000 - 1_000))],
  ["invalid UTF-8", () => Buffer.from([0x7b, 0xff, 0x7d, 0x0a])],
];

for (const [name, make] of malformed) {
  test(`malformed helper output is refused: ${name}`, async () => {
    const { h, c } = await started();
    await h.advance(0);
    const token = jwt(h.clock.now + 300_000);
    const raw = make(token);
    h.child.stdout.emit("data", Buffer.from(raw));
    h.child.end(0, null);
    await flush();
    assert.equal(c.servers().has("jocasta"), false);
    assert.equal(parseHelperOutput(Buffer.from(raw), 1_900_000_000_000), undefined);
    await h.advance(15_000);
    assert.equal(h.spawns.length, 2, "retried at the bounded interval");
  });
}

test("nonzero exit, signal, spawn error and spawn throw all fail closed", async () => {
  for (const end of [(child, t) => child.reply(output(t), 3), (child) => child.end(null, "SIGTERM"),
    (child) => { child.pid = undefined; child.emit("error", new Error("ENOENT " + HELPER)); }]) {
    const { h, c } = await started();
    await h.advance(0);
    end(h.child, jwt(h.clock.now + 300_000));
    await flush();
    assert.equal(c.servers().has("jocasta"), false);
  }
  const { h, c } = await started({ spawnThrows: true });
  await h.advance(0);
  assert.equal(c.servers().has("jocasta"), false);
  await h.advance(15_000);
  assert.equal(h.spawns.length, 2);
});

test("oversized output and a hung helper are killed and refused", async () => {
  const big = await started();
  await big.h.advance(0);
  big.h.child.stdout.emit("data", Buffer.alloc(16_385, 0x61));
  await flush();
  assert.deepEqual(big.h.child.signals, ["SIGKILL"]);
  assert.equal(big.c.servers().has("jocasta"), false);

  const hung = await started();
  await hung.h.advance(0);
  await hung.h.advance(11_999);
  assert.deepEqual(hung.h.child.signals, []);
  await hung.h.advance(1);
  assert.deepEqual(hung.h.child.signals, ["SIGKILL"]);
  assert.equal(hung.c.servers().has("jocasta"), false);
  await hung.h.advance(15_000);
  assert.equal(hung.h.spawns.length, 2);
});

test("a foreign reserved entry is never overwritten and no token is minted", async () => {
  const user = { type: "remote", url: "https://user.example/mcp", headers: { Authorization: "user-credential" } };
  const { h, c } = await started({ initial: { jocasta: user, unrelated } });
  await h.advance(60_000);
  assert.equal(h.spawns.length, 0);
  assert.deepEqual(c.servers().get("jocasta"), user);
  c.base.delete("jocasta");
  c.rebuild();
  await h.advance(15_000);
  assert.equal(h.spawns.length, 1);
  const token = jwt(h.clock.now + 300_000);
  h.child.reply(output(token));
  await flush();
  assert.deepEqual(c.servers().get("jocasta"), expected(token));
});

test("a collision appearing later withholds and drops the held token", async () => {
  const { h, c } = await withToken();
  const user = { type: "remote", url: "https://user.example/mcp", oauth: false };
  c.base.set("jocasta", user);
  c.rebuild();
  assert.deepEqual(c.servers().get("jocasta"), user);
  await h.advance(145_000);
  assert.equal(h.spawns.length, 1, "no refresh while colliding");
  assert.deepEqual(c.servers().get("jocasta"), user);
});

test("cleanup kills and awaits the in-flight helper, clears timers and disposes only its own transform", async () => {
  const { h, c, cleanup } = await withToken();
  const other = await c.ctx.mcp.transform((editor) => editor.set("other", unrelated));
  await h.advance(145_000);
  const child = h.child;
  let done = false;
  const finished = cleanup().then(() => { done = true; });
  await flush();
  assert.deepEqual(child.signals, ["SIGTERM"]);
  await finished;
  assert.equal(done, true);
  assert.equal(c.disposed.length, 1);
  assert.equal(c.transforms.length, 1, "the other plugin's transform remains");
  assert.equal(c.servers().has("jocasta"), false);
  assert.deepEqual(c.servers().get("other"), unrelated);
  assert.equal(h.timers.size, 0);
  // A late reply from the killed child cannot reinstate anything.
  child.emit("close", 0, null);
  await h.advance(600_000);
  assert.equal(h.spawns.length, 2);
  c.rebuild();
  assert.equal(c.servers().has("jocasta"), false);
  await other.dispose();
});

test("cleanup escalates to SIGKILL when the helper ignores SIGTERM", async () => {
  const { h, c, cleanup } = await withToken();
  await h.advance(145_000);
  const child = h.child;
  child.onSignal = (signal) => { if (signal === "SIGKILL") child.end(null, signal); };
  let done = false;
  const finished = cleanup().then(() => { done = true; });
  await h.advance(1_999);
  assert.equal(done, false);
  await h.advance(1);
  await finished;
  assert.deepEqual(child.signals, ["SIGTERM", "SIGKILL"]);
  assert.equal(c.servers().has("jocasta"), false);
  assert.equal(h.timers.size, 0);
});

test("locations are independent instances", async () => {
  const h = harness();
  const first = context({ unrelated });
  const second = context({ unrelated });
  const instance = createPlugin(h.runtime);
  const stopFirst = await instance.setup(first.ctx);
  await instance.setup(second.ctx);
  await h.advance(0);
  assert.equal(h.spawns.length, 2);
  const [a, b] = h.children;
  const ta = jwt(h.clock.now + 300_000, "a");
  const tb = jwt(h.clock.now + 300_000, "b");
  a.reply(output(ta));
  b.reply(output(tb));
  await flush();
  assert.deepEqual(first.servers().get("jocasta"), expected(ta));
  assert.deepEqual(second.servers().get("jocasta"), expected(tb));
  await stopFirst();
  assert.equal(first.servers().has("jocasta"), false);
  assert.deepEqual(second.servers().get("jocasta"), expected(tb));
  await h.advance(145_000);
  assert.equal(h.spawns.length, 3, "only the live location refreshes");
});

test("a throwing editor never escapes the transform", async () => {
  const h = harness();
  const c = context({ unrelated });
  const throwing = { get: () => { throw new Error("editor"); } };
  await createPlugin(h.runtime).setup(c.ctx);
  assert.doesNotThrow(() => c.transforms[0].run(throwing));
});

const refusals = [
  ["older OpenCode", { context: { version: "2.1.3" } }],
  ["newer OpenCode", { context: { version: "2.1.5" } }],
  ["no app metadata", { context: { version: null } }],
  ["missing version", { context: { version: "" } }],
  ["another UID", { runtime: { getuid: () => uid + 1 } }],
  ["another HOME", { runtime: { env: { HOME: home + "-limited" } } }],
  ["missing HOME", { runtime: { env: {} } }],
  ["private config dir", { runtime: { env: { HOME: home, OPENCODE_CONFIG_DIR: home + "/private" } } }],
  ["foreign XDG config", { runtime: { env: { HOME: home, XDG_CONFIG_HOME: home + "/limited/.config" } } }],
  ["realpath failure", { runtime: { realpath: () => { throw new Error("missing"); } } }],
];

for (const [name, options] of refusals) {
  test(`refuses without any transform or helper: ${name}`, async () => {
    const user = { type: "remote", url: "https://user.example/mcp" };
    const { h, c, cleanup } = await started({ ...options, initial: { jocasta: user, unrelated } });
    assert.equal(cleanup, undefined);
    assert.equal(c.transforms.length, 0);
    await h.advance(60_000);
    assert.equal(h.spawns.length, 0);
  });
}

test("the ordinary XDG config location is admitted", async () => {
  const { h } = await started({ runtime: { env: { HOME: home, XDG_CONFIG_HOME: home + "/.config" } } });
  await h.advance(0);
  assert.equal(h.spawns.length, 1);
});

test("a copy outside the ordinary plugin path refuses, as the default export and with a fake runtime", async () => {
  const limited = path.join(home, "limited-profile/home/.config/opencode/plugins");
  await mkdir(limited, { recursive: true });
  const copy = path.join(limited, "webmcp-jocasta.js");
  await copyFile(pluginPath, copy);
  const { h, c } = await started({ runtime: { modulePath: copy } });
  assert.equal(c.transforms.length, 0);
  await h.advance(1_000);
  assert.equal(h.spawns.length, 0);
  // The copy's own default runtime: its module path is the copy, so it refuses
  // before reaching spawn even with the supported version.
  const copied = await import(pathToFileURL(copy).href);
  const other = context({ unrelated });
  assert.equal(await copied.default.setup(other.ctx), undefined);
  assert.equal(other.transforms.length, 0);
});

test("the default export refuses an unsupported version without spawning", async () => {
  const c = context({ unrelated }, { version: "2.0.30" });
  assert.equal(await plugin.default.setup(c.ctx), undefined);
  assert.equal(c.transforms.length, 0);
});

test("nothing was logged", () => {
  assert.deepEqual(consoleCalls, []);
});
