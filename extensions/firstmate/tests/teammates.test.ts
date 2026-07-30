import assert from "node:assert/strict";
import test from "node:test";
import { discoverTeammates } from "../teammates.ts";

test("bundled crew is runnable with explicit tool allowlists", () => {
  const crew = discoverTeammates("/tmp/no-firstmate-project", false);
  assert.deepEqual(crew.map((teammate) => teammate.name), ["planner", "reviewer", "scout", "worker"]);
  for (const teammate of crew) {
    assert.ok(teammate.tools.length > 0);
    assert.equal(teammate.tools.includes("firstmate_delegate"), false);
  }
});
