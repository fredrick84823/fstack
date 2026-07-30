import assert from "node:assert/strict";
import { chmod, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { runPiTask } from "../delegation.ts";
import type { Teammate } from "../teammates.ts";

const teammate: Teammate = {
  name: "fake",
  description: "fake teammate",
  tools: ["read"],
  systemPrompt: "test prompt",
  source: "bundled",
  filePath: "fake.md",
};

async function fakePiScript(): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "firstmate-fake-pi-"));
  const script = join(dir, "fake-pi.mjs");
  await writeFile(
    script,
    `#!/usr/bin/env node
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
if (process.env.FIRSTMATE_FAKE_MODE === "abort") {
  const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { stdio: "ignore" });
  writeFileSync(process.env.FIRSTMATE_FAKE_PID_FILE, String(child.pid));
  setInterval(() => {}, 1000);
} else {
  console.log(JSON.stringify({
    type: "message_end",
    message: {
      role: "assistant",
      content: [{ type: "text", text: "fake result" }],
      api: "test",
      provider: "test",
      model: "fake-model",
      usage: { input: 2, output: 3, cacheRead: 4, cacheWrite: 5, totalTokens: 14, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0.25 } },
      stopReason: "stop",
      timestamp: Date.now()
    }
  }));
}
`,
    { mode: 0o700 },
  );
  await chmod(script, 0o700);
  return script;
}

test("Pi subprocess JSON is parsed into bounded delegation output and usage", async () => {
  const script = await fakePiScript();
  process.env.FIRSTMATE_PI_COMMAND = script;
  process.env.FIRSTMATE_FAKE_MODE = "complete";
  try {
    const result = await runPiTask({ teammate: "fake", task: "test" }, teammate, { cwd: process.cwd() });
    assert.equal(result.status, "completed");
    assert.equal(result.output, "fake result");
    assert.equal(result.model, "fake-model");
    assert.deepEqual(result.usage, { input: 2, output: 3, cacheRead: 4, cacheWrite: 5, cost: 0.25, turns: 1 });
  } finally {
    delete process.env.FIRSTMATE_PI_COMMAND;
    delete process.env.FIRSTMATE_FAKE_MODE;
  }
});

test("abort terminates the delegated subprocess group", async () => {
  if (process.platform === "win32") return;
  const script = await fakePiScript();
  const pidFile = join(await mkdtemp(join(tmpdir(), "firstmate-pid-")), "pid");
  process.env.FIRSTMATE_PI_COMMAND = script;
  process.env.FIRSTMATE_FAKE_MODE = "abort";
  process.env.FIRSTMATE_FAKE_PID_FILE = pidFile;
  const controller = new AbortController();
  try {
    const promise = runPiTask({ teammate: "fake", task: "wait" }, teammate, {
      cwd: process.cwd(),
      signal: controller.signal,
    });
    let childPid: number | undefined;
    for (let attempt = 0; attempt < 50; attempt++) {
      try {
        childPid = Number(await readFile(pidFile, "utf8"));
        break;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 10));
      }
    }
    assert.ok(childPid);
    controller.abort();
    const result = await promise;
    assert.equal(result.status, "aborted");
    await new Promise((resolve) => setTimeout(resolve, 50));
    assert.throws(() => process.kill(childPid!, 0), /ESRCH/);
  } finally {
    delete process.env.FIRSTMATE_PI_COMMAND;
    delete process.env.FIRSTMATE_FAKE_MODE;
    delete process.env.FIRSTMATE_FAKE_PID_FILE;
  }
});
