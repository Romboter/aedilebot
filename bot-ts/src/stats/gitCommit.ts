// Short commit hash by reading .git directly: no child process, so it works
// without Deno's --allow-run. Returns "unknown" on any failure.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export function readGitCommit(startDir: string): string {
  try {
    let dir = path.resolve(startDir);
    for (;;) {
      const gitDir = path.join(dir, ".git");
      if (existsSync(path.join(gitDir, "HEAD"))) {
        const head = readFileSync(path.join(gitDir, "HEAD"), "utf8").trim();
        const ref = /^ref: (.+)$/.exec(head)?.[1];
        const hash = ref ? readFileSync(path.join(gitDir, ref), "utf8").trim() : head;
        return /^[0-9a-f]{7,}$/.test(hash) ? hash.slice(0, 7) : "unknown";
      }
      const parent = path.dirname(dir);
      if (parent === dir) return "unknown";
      dir = parent;
    }
  } catch {
    return "unknown";
  }
}
