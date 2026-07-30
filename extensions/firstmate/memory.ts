import { createHash, randomUUID } from "node:crypto";
import { existsSync, realpathSync } from "node:fs";
import { appendFile, chmod, mkdir, readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export type MemoryScope = "global" | "project";
export type MemoryKind = "thought" | "fact" | "delegation";

export interface MemoryRecord {
  version: 1;
  id: string;
  operation: "remember" | "forget";
  scope: MemoryScope;
  kind?: MemoryKind;
  text?: string;
  tags?: string[];
  targetId?: string;
  projectKey?: string;
  createdAt: string;
}

export interface RememberInput {
  text: string;
  cwd: string;
  scope?: MemoryScope;
  kind?: MemoryKind;
  tags?: string[];
}

export interface RecallInput {
  query?: string;
  cwd: string;
  scope?: MemoryScope | "all";
  limit?: number;
}

export interface MemoryStats {
  active: number;
  forgotten: number;
  files: number;
}

const MAX_MEMORY_BYTES = 24 * 1024;
const MAX_RECALL_BYTES = 16 * 1024;
const DEFAULT_LIMIT = 8;

const SECRET_PATTERNS = [
  /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/i,
  /\b(?:sk|pk|ghp|github_pat|xox[baprs])-[-_a-z0-9]{16,}\b/i,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b/,
  /\bAuthorization\s*:\s*Bearer\s+\S+/i,
  /\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret|token)\s*[:=]\s*[^\s]{8,}/i,
  /\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis):\/\/[^\s:@/]+:[^\s@/]+@/i,
];

function tokenize(value: string): Set<string> {
  return new Set(
    value
      .toLowerCase()
      .split(/[^\p{L}\p{N}_-]+/u)
      .filter((token) => token.length > 1),
  );
}

export function canonicalProjectRoot(cwd: string): string {
  let current: string;
  try {
    current = realpathSync(cwd);
  } catch {
    current = resolve(cwd);
  }
  const startingDirectory = current;
  while (true) {
    if (existsSync(join(current, ".git"))) return current;
    const parent = dirname(current);
    if (parent === current) return startingDirectory;
    current = parent;
  }
}

function projectKey(cwd: string): string {
  return createHash("sha256").update(canonicalProjectRoot(cwd)).digest("hex").slice(0, 24);
}

function scoreMemory(record: MemoryRecord, queryTokens: Set<string>): number {
  if (queryTokens.size === 0) return 0;
  const textTokens = tokenize(`${record.text ?? ""} ${(record.tags ?? []).join(" ")}`);
  let score = 0;
  for (const token of queryTokens) {
    if (textTokens.has(token)) score += record.tags?.includes(token) ? 3 : 1;
  }
  return score;
}

function activeRecords(records: MemoryRecord[]): MemoryRecord[] {
  const forgotten = new Set(records.filter((record) => record.operation === "forget").map((record) => record.targetId));
  return records.filter((record) => record.operation === "remember" && !forgotten.has(record.id));
}

async function readJsonl(filePath: string): Promise<MemoryRecord[]> {
  let content: string;
  try {
    content = await readFile(filePath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }

  const records: MemoryRecord[] = [];
  for (const line of content.split("\n")) {
    if (!line.trim()) continue;
    try {
      const record = JSON.parse(line) as MemoryRecord;
      if (record.version === 1 && record.id && record.operation) records.push(record);
    } catch {
      // Preserve availability if a process was interrupted during an append.
    }
  }
  return records;
}

export function containsLikelySecret(text: string): boolean {
  return SECRET_PATTERNS.some((pattern) => pattern.test(text));
}

export class MemoryStore {
  readonly rootDir: string;

  constructor(rootDir = join(getAgentDir(), "firstmate", "memory")) {
    this.rootDir = rootDir;
  }

  async remember(input: RememberInput): Promise<MemoryRecord> {
    const text = input.text.trim();
    if (!text) throw new Error("Memory text cannot be empty");
    if (Buffer.byteLength(text, "utf8") > MAX_MEMORY_BYTES) {
      throw new Error(`Memory exceeds ${MAX_MEMORY_BYTES} bytes`);
    }
    if (containsLikelySecret(text)) {
      throw new Error("Refusing to memorize text that looks like a credential or private key");
    }

    const scope = input.scope ?? "project";
    const record: MemoryRecord = {
      version: 1,
      id: randomUUID(),
      operation: "remember",
      scope,
      kind: input.kind ?? "fact",
      text,
      tags: input.tags?.map((tag) => tag.trim().toLowerCase()).filter(Boolean),
      projectKey: scope === "project" ? projectKey(input.cwd) : undefined,
      createdAt: new Date().toISOString(),
    };
    await this.append(record, input.cwd);
    return record;
  }

  async forget(id: string, cwd: string, scope: MemoryScope | "all" = "all"): Promise<MemoryScope[]> {
    const candidates: Array<{ scope: MemoryScope; records: MemoryRecord[] }> = [];
    if (scope === "all" || scope === "global") {
      candidates.push({ scope: "global", records: await readJsonl(this.globalPath()) });
    }
    if (scope === "all" || scope === "project") {
      candidates.push({ scope: "project", records: await readJsonl(this.projectPath(cwd)) });
    }

    const forgottenScopes: MemoryScope[] = [];
    for (const candidate of candidates) {
      if (!activeRecords(candidate.records).some((record) => record.id === id)) continue;
      const record: MemoryRecord = {
        version: 1,
        id: randomUUID(),
        operation: "forget",
        scope: candidate.scope,
        targetId: id,
        projectKey: candidate.scope === "project" ? projectKey(cwd) : undefined,
        createdAt: new Date().toISOString(),
      };
      await this.append(record, cwd);
      forgottenScopes.push(candidate.scope);
    }
    if (forgottenScopes.length === 0) throw new Error(`Memory ${id} was not found in scope ${scope}`);
    return forgottenScopes;
  }

  async recall(input: RecallInput): Promise<MemoryRecord[]> {
    const scope = input.scope ?? "all";
    const records: MemoryRecord[] = [];
    if (scope === "all" || scope === "global") records.push(...(await readJsonl(this.globalPath())));
    if (scope === "all" || scope === "project") records.push(...(await readJsonl(this.projectPath(input.cwd))));

    const queryTokens = tokenize(input.query ?? "");
    const sorted = activeRecords(records)
      .map((record, index) => ({ record, index, score: scoreMemory(record, queryTokens) }))
      .filter(({ score }) => queryTokens.size === 0 || score > 0)
      .sort((a, b) => b.score - a.score || b.index - a.index)
      .map(({ record }) => record);

    const result: MemoryRecord[] = [];
    let bytes = 0;
    for (const record of sorted) {
      if (result.length >= Math.min(Math.max(input.limit ?? DEFAULT_LIMIT, 1), 50)) break;
      const size = Buffer.byteLength(JSON.stringify(record), "utf8");
      if (bytes + size > MAX_RECALL_BYTES) break;
      result.push(record);
      bytes += size;
    }
    return result;
  }

  async stats(cwd: string): Promise<MemoryStats> {
    const records = [...(await readJsonl(this.globalPath())), ...(await readJsonl(this.projectPath(cwd)))];
    return {
      active: activeRecords(records).length,
      forgotten: records.filter((record) => record.operation === "forget").length,
      files: 2,
    };
  }

  private globalPath(): string {
    return join(this.rootDir, "global.jsonl");
  }

  private projectPath(cwd: string): string {
    return join(this.rootDir, "projects", `${projectKey(cwd)}.jsonl`);
  }

  private async append(record: MemoryRecord, cwd: string): Promise<void> {
    const filePath = record.scope === "global" ? this.globalPath() : this.projectPath(cwd);
    await mkdir(join(this.rootDir, "projects"), { recursive: true, mode: 0o700 });
    await chmod(this.rootDir, 0o700).catch(() => undefined);
    await chmod(join(this.rootDir, "projects"), 0o700).catch(() => undefined);
    await appendFile(filePath, `${JSON.stringify(record)}\n`, { encoding: "utf8", mode: 0o600, flag: "a" });
    await chmod(filePath, 0o600).catch(() => undefined);
  }
}
