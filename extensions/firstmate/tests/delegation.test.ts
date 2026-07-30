import assert from "node:assert/strict";
import test from "node:test";
import { delegateTasks, truncateUtf8, type DelegationResult, type TaskRunner } from "../delegation.ts";
import type { Teammate } from "../teammates.ts";

const teammate = (name: string): Teammate => ({
  name,
  description: `${name} teammate`,
  tools: ["read"],
  systemPrompt: "Be useful",
  source: "bundled",
  filePath: `${name}.md`,
});

const result = (name: string, task: string): DelegationResult => ({
  teammate: name,
  task,
  status: "completed",
  output: `done:${task}`,
  usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 1 },
});

test("delegation preserves task order while bounding concurrency", async () => {
  let active = 0;
  let peak = 0;
  const runner: TaskRunner = async (task) => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise((resolve) => setTimeout(resolve, task.task === "slow" ? 30 : 5));
    active -= 1;
    return result(task.teammate, task.task);
  };

  const results = await delegateTasks(
    [
      { teammate: "scout", task: "slow" },
      { teammate: "reviewer", task: "fast" },
      { teammate: "scout", task: "last" },
    ],
    [teammate("scout"), teammate("reviewer")],
    { cwd: "/work", concurrency: 2, runner },
  );

  assert.equal(peak, 2);
  assert.deepEqual(results.map((item) => item.task), ["slow", "fast", "last"]);
});

test("delegation validates teammate names before spawning", async () => {
  let called = false;
  const runner: TaskRunner = async (task) => {
    called = true;
    return result(task.teammate, task.task);
  };
  await assert.rejects(
    delegateTasks([{ teammate: "ghost", task: "work" }], [teammate("scout")], { cwd: "/work", runner }),
    /Unknown teammate/,
  );
  assert.equal(called, false);
});

test("UTF-8 truncation stays within complete characters", () => {
  const truncated = truncateUtf8("🙂🙂🙂", 5);
  assert.equal(truncated.includes("�"), false);
  assert.match(truncated, /Output truncated/);
});
