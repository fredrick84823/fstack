import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CONFIG_DIR_NAME, getAgentDir, parseFrontmatter } from "@earendil-works/pi-coding-agent";

export interface Teammate {
  name: string;
  description: string;
  tools: string[];
  model?: string;
  systemPrompt: string;
  source: "bundled" | "user" | "project";
  filePath: string;
}

const BUNDLED_DIR = join(dirname(fileURLToPath(import.meta.url)), "teammates");

function loadDirectory(dir: string, source: Teammate["source"]): Teammate[] {
  if (!existsSync(dir)) return [];
  let entries: string[];
  try {
    entries = readdirSync(dir).filter((entry) => entry.endsWith(".md"));
  } catch {
    return [];
  }

  const teammates: Teammate[] = [];
  for (const entry of entries) {
    const filePath = join(dir, entry);
    try {
      if (!statSync(filePath).isFile()) continue;
      const { frontmatter, body } = parseFrontmatter<Record<string, string>>(readFileSync(filePath, "utf8"));
      const tools = frontmatter.tools?.split(",").map((tool) => tool.trim()).filter(Boolean) ?? [];
      if (!frontmatter.name || !frontmatter.description || tools.length === 0) continue;
      teammates.push({
        name: frontmatter.name,
        description: frontmatter.description,
        tools,
        model: frontmatter.model || undefined,
        systemPrompt: body.trim(),
        source,
        filePath,
      });
    } catch {
      // Ignore invalid teammate files; listCrew surfaces only runnable definitions.
    }
  }
  return teammates;
}

function nearestProjectTeamDir(cwd: string): string | undefined {
  let current = cwd;
  while (true) {
    const candidate = join(current, CONFIG_DIR_NAME, "firstmate", "teammates");
    try {
      if (statSync(candidate).isDirectory()) return candidate;
    } catch {
      // Keep walking.
    }
    const parent = dirname(current);
    if (parent === current) return undefined;
    current = parent;
  }
}

export function discoverTeammates(cwd: string, includeProject: boolean): Teammate[] {
  const map = new Map<string, Teammate>();
  for (const teammate of loadDirectory(BUNDLED_DIR, "bundled")) map.set(teammate.name, teammate);
  for (const teammate of loadDirectory(join(getAgentDir(), "firstmate", "teammates"), "user")) {
    map.set(teammate.name, teammate);
  }
  if (includeProject) {
    const projectDir = nearestProjectTeamDir(cwd);
    if (projectDir) {
      for (const teammate of loadDirectory(projectDir, "project")) map.set(teammate.name, teammate);
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function formatCrew(teammates: Teammate[]): string {
  if (teammates.length === 0) return "No teammates are configured.";
  return teammates.map((teammate) => `- ${teammate.name} (${teammate.source}): ${teammate.description}`).join("\n");
}
