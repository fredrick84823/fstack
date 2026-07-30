import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import type { Message } from "@earendil-works/pi-ai";
import type { Teammate } from "./teammates.ts";

export interface DelegatedTask {
  teammate: string;
  task: string;
  cwd?: string;
}

export interface DelegationUsage {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  cost: number;
  turns: number;
}

export interface DelegationResult {
  teammate: string;
  task: string;
  status: "completed" | "failed" | "aborted";
  output: string;
  error?: string;
  model?: string;
  usage: DelegationUsage;
}

export interface DelegateOptions {
  cwd: string;
  parentModel?: string;
  signal?: AbortSignal;
  onUpdate?: (results: DelegationResult[]) => void;
  concurrency?: number;
  runner?: TaskRunner;
}

export type TaskRunner = (
  task: DelegatedTask,
  teammate: Teammate,
  options: Pick<DelegateOptions, "cwd" | "parentModel" | "signal">,
) => Promise<DelegationResult>;

const MAX_TASKS = 8;
const DEFAULT_CONCURRENCY = 4;
const OUTPUT_CAP_BYTES = 50 * 1024;
const STDERR_CAP_BYTES = 16 * 1024;
const JSON_EVENT_CAP_BYTES = 2 * 1024 * 1024;

function emptyUsage(): DelegationUsage {
  return { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 0 };
}

function assistantText(message: Message): string {
  if (message.role !== "assistant") return "";
  return message.content.filter((part) => part.type === "text").map((part) => part.text).join("\n").trim();
}

export function truncateUtf8(value: string, cap = OUTPUT_CAP_BYTES): string {
  const originalBytes = Buffer.byteLength(value, "utf8");
  if (originalBytes <= cap) return value;
  let bytes = Buffer.from(value, "utf8").subarray(0, cap);
  while (bytes.length > 0 && (bytes[bytes.length - 1] & 0b1100_0000) === 0b1000_0000) bytes = bytes.subarray(0, -1);
  const text = bytes.toString("utf8").replace(/\uFFFD$/u, "");
  return `${text}\n\n[Output truncated: ${originalBytes - Buffer.byteLength(text, "utf8")} bytes omitted]`;
}

function invocation(args: string[]): { command: string; args: string[] } {
  if (process.env.FIRSTMATE_PI_COMMAND) return { command: process.env.FIRSTMATE_PI_COMMAND, args };
  const script = process.argv[1];
  const bunVirtual = script?.startsWith("/$bunfs/root/");
  if (script && !bunVirtual && existsSync(script)) return { command: process.execPath, args: [script, ...args] };
  const executable = basename(process.execPath).toLowerCase();
  return /^(node|bun)(\.exe)?$/.test(executable)
    ? { command: "pi", args }
    : { command: process.execPath, args };
}

export async function runPiTask(
  task: DelegatedTask,
  teammate: Teammate,
  options: Pick<DelegateOptions, "cwd" | "parentModel" | "signal">,
): Promise<DelegationResult> {
  const usage = emptyUsage();
  let finalOutput = "";
  let stderr = "";
  let stopReason: string | undefined;
  let errorMessage: string | undefined;
  let model = teammate.model;
  let promptDir: string | undefined;
  let aborted = false;

  try {
    promptDir = await mkdtemp(join(tmpdir(), "firstmate-"));
    const promptPath = join(promptDir, `${teammate.name.replace(/[^a-z0-9_.-]/gi, "_")}.md`);
    await writeFile(promptPath, teammate.systemPrompt, { encoding: "utf8", mode: 0o600 });

    const args = ["--mode", "json", "-p", "--no-session", "--tools", teammate.tools.join(",")];
    const selectedModel = teammate.model ?? options.parentModel;
    if (selectedModel) args.push("--model", selectedModel);
    args.push("--append-system-prompt", promptPath, `Task: ${task.task}`);

    const child = invocation(args);
    const exitCode = await new Promise<number>((resolve) => {
      const detached = process.platform !== "win32";
      const processHandle = spawn(child.command, child.args, {
        cwd: task.cwd ?? options.cwd,
        shell: false,
        detached,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, FIRSTMATE_CHILD: "1" },
      });
      let stdoutBuffer = "";
      let killTimer: NodeJS.Timeout | undefined;
      let settled = false;

      const killTree = (signal: NodeJS.Signals) => {
        if (!processHandle.pid) return;
        try {
          if (detached) process.kill(-processHandle.pid, signal);
          else processHandle.kill(signal);
        } catch {
          // The process may already have exited.
        }
      };
      const abort = () => {
        aborted = true;
        killTree("SIGTERM");
        killTimer = setTimeout(() => killTree("SIGKILL"), 5_000);
        killTimer.unref();
      };
      const finish = (code: number) => {
        if (settled) return;
        settled = true;
        if (killTimer) clearTimeout(killTimer);
        options.signal?.removeEventListener("abort", abort);
        resolve(code);
      };
      const overflow = () => {
        errorMessage = `Pi emitted a JSON event larger than ${JSON_EVENT_CAP_BYTES} bytes`;
        killTree("SIGTERM");
      };
      const processLine = (line: string) => {
        if (!line.trim()) return;
        if (Buffer.byteLength(line, "utf8") > JSON_EVENT_CAP_BYTES) {
          overflow();
          return;
        }
        try {
          const event = JSON.parse(line) as { type?: string; message?: Message };
          if (event.type !== "message_end" || !event.message || event.message.role !== "assistant") return;
          finalOutput = truncateUtf8(assistantText(event.message));
          usage.turns += 1;
          usage.input += event.message.usage?.input ?? 0;
          usage.output += event.message.usage?.output ?? 0;
          usage.cacheRead += event.message.usage?.cacheRead ?? 0;
          usage.cacheWrite += event.message.usage?.cacheWrite ?? 0;
          usage.cost += event.message.usage?.cost?.total ?? 0;
          stopReason = event.message.stopReason;
          errorMessage = event.message.errorMessage ?? errorMessage;
          model = event.message.model ?? model;
        } catch {
          // Ignore non-JSON diagnostics and malformed partial lines.
        }
      };

      processHandle.stdout.on("data", (chunk) => {
        stdoutBuffer += chunk.toString();
        const lines = stdoutBuffer.split("\n");
        stdoutBuffer = lines.pop() ?? "";
        for (const line of lines) processLine(line);
        if (Buffer.byteLength(stdoutBuffer, "utf8") > JSON_EVENT_CAP_BYTES) overflow();
      });
      processHandle.stderr.on("data", (chunk) => {
        stderr = truncateUtf8(stderr + chunk.toString(), STDERR_CAP_BYTES);
      });
      processHandle.on("error", (error) => {
        errorMessage = error.message;
        finish(1);
      });
      processHandle.on("close", (code) => {
        if (stdoutBuffer.trim()) processLine(stdoutBuffer);
        finish(code ?? 1);
      });

      if (options.signal?.aborted) abort();
      else options.signal?.addEventListener("abort", abort, { once: true });
    });

    const output = finalOutput;
    const failed = exitCode !== 0 || stopReason === "error" || stopReason === "aborted";
    return {
      teammate: teammate.name,
      task: task.task,
      status: aborted || stopReason === "aborted" ? "aborted" : failed ? "failed" : "completed",
      output: output || (failed ? "" : "(no output)"),
      error: failed ? errorMessage || stderr || `Pi exited with code ${exitCode}` : undefined,
      model,
      usage,
    };
  } finally {
    if (promptDir) await rm(promptDir, { recursive: true, force: true });
  }
}

export async function delegateTasks(
  tasks: DelegatedTask[],
  teammates: Teammate[],
  options: DelegateOptions,
): Promise<DelegationResult[]> {
  if (tasks.length < 1 || tasks.length > MAX_TASKS) throw new Error(`Delegation requires 1-${MAX_TASKS} tasks`);
  const byName = new Map(teammates.map((teammate) => [teammate.name, teammate]));
  for (const task of tasks) {
    if (!task.task.trim()) throw new Error(`Task for ${task.teammate} cannot be empty`);
    if (!byName.has(task.teammate)) {
      throw new Error(`Unknown teammate "${task.teammate}". Available: ${[...byName.keys()].join(", ") || "none"}`);
    }
  }

  const runner = options.runner ?? runPiTask;
  const results: DelegationResult[] = new Array(tasks.length);
  let next = 0;
  const concurrency = Math.min(Math.max(options.concurrency ?? DEFAULT_CONCURRENCY, 1), tasks.length);
  const workers = Array.from({ length: concurrency }, async () => {
    while (true) {
      const index = next++;
      if (index >= tasks.length) return;
      const task = tasks[index];
      results[index] = await runner(task, byName.get(task.teammate)!, options);
      options.onUpdate?.(results.filter(Boolean));
    }
  });
  await Promise.all(workers);
  return results;
}

export function formatDelegationResults(results: DelegationResult[]): string {
  return results
    .map((result) => {
      const heading = `### ${result.teammate}: ${result.status}`;
      const body = result.status === "completed" ? result.output : result.error || result.output || "Unknown failure";
      return `${heading}\n\n${body}`;
    })
    .join("\n\n---\n\n");
}
