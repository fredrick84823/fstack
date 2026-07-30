import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { MemoryStore, containsLikelySecret } from "../memory.ts";

test("memory survives restart, scopes recall, and forgets by tombstone", async () => {
  const root = await mkdtemp(join(tmpdir(), "firstmate-memory-test-"));
  const cwd = "/work/project-a";
  const store = new MemoryStore(root);
  const project = await store.remember({ text: "Prefer vertical slices", cwd, scope: "project", tags: ["architecture"] });
  const global = await store.remember({ text: "Use concise reports", cwd, scope: "global" });

  const restarted = new MemoryStore(root);
  assert.deepEqual((await restarted.recall({ query: "vertical architecture", cwd })).map((record) => record.id), [project.id]);
  assert.equal((await restarted.recall({ cwd, scope: "all" })).length, 2);

  await restarted.forget(project.id, cwd, "project");
  assert.equal((await restarted.recall({ query: "vertical", cwd })).length, 0);
  assert.deepEqual(await restarted.forget(global.id, cwd), ["global"]);
  assert.equal((await restarted.recall({ query: "concise", cwd, scope: "global" })).length, 0);
  await assert.rejects(restarted.forget(global.id, cwd), /was not found/);
});

test("memory storage uses opaque project names and restrictive permissions", async () => {
  const root = await mkdtemp(join(tmpdir(), "firstmate-memory-mode-"));
  const cwd = "/Users/example/secret-project-name";
  const store = new MemoryStore(root);
  await store.remember({ text: "A durable decision", cwd, scope: "project" });

  const projectsDir = join(root, "projects");
  const entries = await import("node:fs/promises").then(({ readdir }) => readdir(projectsDir));
  assert.equal(entries.length, 1);
  assert.equal(entries[0].includes("secret-project-name"), false);
  assert.equal((await stat(projectsDir)).mode & 0o777, 0o700);
  assert.equal((await stat(join(projectsDir, entries[0]))).mode & 0o777, 0o600);
  assert.match(await readFile(join(projectsDir, entries[0]), "utf8"), /A durable decision/);
});

test("subdirectories of one git repository share project memory", async () => {
  const root = await mkdtemp(join(tmpdir(), "firstmate-memory-repo-"));
  const repo = join(root, "repo");
  const nested = join(repo, "packages", "app");
  await mkdir(join(repo, ".git"), { recursive: true });
  await mkdir(nested, { recursive: true });
  const store = new MemoryStore(join(root, "memory"));
  await store.remember({ text: "Shared repository decision", cwd: repo, scope: "project" });
  assert.equal((await store.recall({ query: "repository decision", cwd: nested, scope: "project" })).length, 1);
});

test("likely secrets are rejected", async () => {
  const secrets = [
    "api_key = super-secret-value-123",
    "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
    "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
    "token=abcdefghijklmnopqrstuvwxyz",
    "postgres://admin:very-secret-password@localhost/db",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop",
  ];
  for (const secret of secrets) assert.equal(containsLikelySecret(secret), true, secret);

  const root = await mkdtemp(join(tmpdir(), "firstmate-memory-secret-"));
  await assert.rejects(
    new MemoryStore(root).remember({ text: "-----BEGIN PRIVATE KEY-----\nabc", cwd: "/work" }),
    /credential or private key/,
  );
});
