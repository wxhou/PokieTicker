import { defineConfig, devices } from '@playwright/test';
import { readFileSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';

// ─── Detect project root (where openspec/ and tests/ live) ───
function findProjectRoot(start: string): string {
  let dir = start;
  for (let i = 0; i < 10; i++) {
    // Project root: has both openspec/ AND tests/ (package.json optional)
    if (existsSync(join(dir, 'openspec')) && existsSync(join(dir, 'tests'))) {
      return dir;
    }
    const parent = join(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  return start;
}

// ─── Find the npm project root (where package.json with scripts lives) ───
function findNpmRoot(projectRoot: string, maxDepth = 5): string {
  function search(dir: string, depth: number): string | null {
    if (depth > maxDepth) return null;
    const pkgPath = join(dir, 'package.json');
    if (existsSync(pkgPath)) {
      try {
        const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
        if (pkg.scripts?.dev || pkg.scripts?.start || pkg.scripts?.serve || pkg.scripts?.preview) {
          return dir;
        }
      } catch {}
    }
    try {
      const entries = readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name === 'node_modules') continue;
        const found = search(join(dir, entry.name), depth + 1);
        if (found) return found;
      }
    } catch {}
    return null;
  }
  return search(projectRoot, 0) ?? projectRoot;
}

const projectRoot = findProjectRoot(__dirname);
const npmRoot = findNpmRoot(projectRoot);

// ─── BASE_URL: prefer env, then seed.spec.ts, then default ───
const seedSpec = join(projectRoot, 'tests', 'playwright', 'seed.spec.ts');
let baseUrl = process.env.BASE_URL || 'http://localhost:3000';
if (existsSync(seedSpec)) {
  const content = readFileSync(seedSpec, 'utf-8');
  const m = content.match(/BASE_URL\s*=\s*process\.env\.BASE_URL\s*\|\|\s*['"]([^'"]+)['"]/);
  if (m) baseUrl = m[1];
}

// ─── Dev command: detect from the npm project ───
let devCmd = 'npm run dev';
const npmPkg = join(npmRoot, 'package.json');
if (existsSync(npmPkg)) {
  const pkg = JSON.parse(readFileSync(npmPkg, 'utf-8'));
  const scripts = pkg.scripts ?? {};
  devCmd = scripts.dev ?? scripts.start ?? scripts.serve ?? scripts.preview ?? devCmd;
  // Prefix with cd if npmRoot differs from projectRoot
  if (npmRoot !== projectRoot) {
    devCmd = `cd ${npmRoot} && ${devCmd}`;
  }
}

export default defineConfig({
  testDir: join(projectRoot, 'tests', 'playwright'),
  outputDir: join(projectRoot, 'tests', 'playwright', 'test-results'),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? (parseInt(process.env.PW_WORKERS || '4') || 4) : undefined,
  reporter: 'list',

  use: {
    baseURL: baseUrl,
    trace: 'on-first-retry',
  },

  // Dev server is already running manually (frontend:7777, backend:8000).
  // No webServer config needed - reuseExistingServer prevents auto-start.

  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: './playwright/.auth/user.json',
      },
      dependencies: ['setup'],
      // E2E tests for screenshot-portfolio may have timing issues in parallel
      // Run these sequentially for stability
      testMatch: /.*\.spec\.ts/,
    },
  ],
});
