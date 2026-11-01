// Merge GitHub links recorded in .meta frontmatter into .meta/sync/github-state.json.
//
// `gitpm push` writes each new issue/milestone number into the entity's frontmatter as soon as
// it is created, but saves github-state.json only when the whole run succeeds. CI keeps the state
// file (on the `gitpm-state` branch), not the frontmatter, so after a run that fails part-way this
// script copies the frontmatter links into the state. Without it, the next run would create the
// same issues again.
//
// Usage (resolve @gitpm/core from the gitpm install): node gitpm_merge_state.mjs <meta-dir>
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { parseTree } from "@gitpm/core";

const metaDir = process.argv[2] ?? ".meta";
const statePath = join(metaDir, "sync", "github-state.json");

const tree = await parseTree(metaDir);
if (!tree.ok) {
  console.error(`gitpm_merge_state: cannot parse ${metaDir}: ${tree.error.message}`);
  process.exit(1);
}

let state;
try {
  state = JSON.parse(await readFile(statePath, "utf-8"));
} catch {
  state = { repo: "", last_sync: new Date().toISOString(), entities: {} };
}

const { milestones, epics, stories } = tree.value;
let added = 0;
for (const entity of [...milestones, ...epics, ...stories]) {
  const gh = entity.github;
  if (!gh) continue;
  const entry = state.entities[entity.id] ?? {};
  const number = entity.type === "milestone" ? gh.milestone_id : gh.issue_number;
  const key = entity.type === "milestone" ? "github_milestone_number" : "github_issue_number";
  if (!number || entry[key]) continue;
  state.entities[entity.id] = {
    ...entry,
    [key]: number,
    local_hash: gh.last_sync_hash ?? "",
    remote_hash: gh.last_sync_hash ?? "",
    synced_at: gh.synced_at ?? new Date().toISOString(),
  };
  state.repo ||= gh.repo ?? "";
  added++;
}

await writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf-8");
console.log(`gitpm_merge_state: ${added} link(s) merged into ${statePath}`);
