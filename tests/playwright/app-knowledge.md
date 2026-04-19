# App Knowledge — 涨讯 (PokieTicker A-share)

Generated: 2026-04-19
Last updated: 2026-04-19

Cross-change E2E knowledge. Updated by Step 4 exploration.

## Routes

SPA with inline routing. No separate pages — all routes rendered within `/`.

| Route | Auth | Page Object | Notes |
|-------|------|-------------|-------|
| `/` (main) | guest | `MainPage.ts` | Stock analysis with candlestick chart, news, predictions |
| `/portfolio` (inline) | required | `MainPage.ts` | Portfolio management with inline login form |
| `/api/auth/login` | - | API endpoint | POST {email, password} → {access_token, user} |
| `/api/auth/register` | - | API endpoint | POST {email, password} → {id, email, created_at} |
| `/api/portfolio` | required | API endpoint | GET/POST with JWT Bearer token |
| `/api/stocks` | - | API endpoint | List/search A-share stocks |
| `/api/predict/{symbol}/forecast` | - | API endpoint | ML forecast (only for BABA/TSLA/AAPL/NVDA/GLD) |

## Credential Format

| Field | Format | Source |
|-------|--------|--------|
| email | `e2e@example.com` | test user via `/api/auth/register` |
| password | `Test1234!` | min 8 chars |
| login endpoint | `/api/auth/login` | needs `/api` prefix (backend uses `prefix="/api"` on auth router) |
| JWT token | Bearer | stored in `localStorage['zx_auth_token']` |

## Common Selector Patterns

Priority: `getByRole` > `getByLabel` > `getByText` > CSS

### Header / Navigation

| Element | Selector | Notes |
|---------|----------|-------|
| Brand name | `getByRole('heading', { name: '涨讯' })` | |
| Brand sub | `getByText('A股事件驱动分析')` | |
| Stock selector dropdown | `getByRole('button', { name: /^[A-Z]{1,5} ▾$/ })` | e.g. "AAPL ▾" |
| Stock search input | `getByRole('textbox', { name: '搜索股票...' })` | |
| Portfolio nav btn | `getByRole('button', { name: '我的持仓' })` | |
| Back to analysis btn | `getByRole('button', { name: '返回分析' })` | |
| GitHub link | `link[href*="github"]` | |

### Portfolio (Inline Login Form)

| Element | Selector | Notes |
|---------|----------|-------|
| Portfolio heading | `getByRole('heading', { name: '我的持仓' })` | |
| Email input | `getByRole('textbox', { name: 'your@email.com' })` | |
| Password input | `getByRole('textbox', { name: '••••••••' })` | |
| Login button | `getByRole('button', { name: '登录' })` | |
| Register button | `getByRole('button', { name: '注册' })` | |
| Logout button | `getByRole('button', { name: '退出登录' })` | |
| Portfolio name input | `getByRole('textbox', { name: /新建组合名称/ })` | |
| Create button | `getByRole('button', { name: '创建' })` | |
| Auth error | `getByText(/登录失败|邮箱或密码错误|该邮箱已被注册|密码长度至少/)` | |
| No portfolios placeholder | `getByText('暂无持仓组合')` | |

### Main Analysis View

| Element | Selector | Notes |
|---------|----------|-------|
| Candlestick chart | `canvas` (first) | SVG/Canvas chart |
| News heading | `getByRole('heading', { name: '新闻' })` | |
| News placeholder | `getByText('点击K线图上的点查看新闻')` | |
| Prediction heading | `getByText('预测')` | |
| ML Disclaimer | `getByText(/ML预测基于美股数据训练|仅供参考不构成投资建议/)` | |

### News Categories

| Element | Selector | Notes |
|---------|----------|-------|
| Market impact | `getByRole('button', { name: /📈 市场影响 \d+ 条/ })` | |
| Policy impact | `getByRole('button', { name: /🏛️ 政策影响 \d+ 条/ })` | |
| Earnings | `getByRole('button', { name: /💰 业绩公告 \d+ 条/ })` | |
| Product/tech | `getByRole('button', { name: /🚀 产品技术 \d+ 条/ })` | |
| Competition | `getByRole('button', { name: /⚔️ 竞争动态 \d+ 条/ })` | |
| Management | `getByRole('button', { name: /👤 管理层变动 \d+ 条/ })` | |

## Architecture

| Aspect | Value | Notes |
|--------|-------|-------|
| Architecture | SPA (React) | Vite dev server + FastAPI backend |
| Frontend | React + Vite, port 7777 | Serves at `/PokieTicker/` path |
| Backend | FastAPI, port 8000 | AKShare data, JWT auth |
| SPA routing | None | Inline route switching via React state |
| Auth method | API-based | JWT stored in `localStorage['zx_auth_token']` |
| Auth UI | Inline in Portfolio component | No separate login page |

## Dynamic Content Conventions

- Stock selector shows US stock codes (AAPL, BABA, TSLA, etc.) — no A-share data in DB yet
- News categories show article counts (e.g., "📈 市场影响 4144 条")
- ML predictions: 404 for non-model stocks (gracefully handled with `.catch(() => null)`)
- Color convention: `--color-up: #ff5252` (red), `--color-down: #00e676` (green) — A-share convention
- Prices displayed with `¥` prefix (CNY)

## Project Conventions

| Convention | Value | Notes |
|------------|-------|-------|
| BASE_URL | `http://localhost:7777/PokieTicker` | Dev frontend |
| Auth token key | `zx_auth_token` | localStorage |
| Last symbol key | `zx_last_symbol` | localStorage |
| Auth method | API | POST `/api/auth/login`, `/api/auth/register` |
| API prefix | `/api` | All API routes use `/api/*` |
| E2E user | `e2e@example.com` / `Test1234!` | Registered via test |

## Selector Fixes (Healer memory)

| Date | Route | Old Selector | New Selector | Reason |
|------|-------|-------------|-------------|--------|
| 2026-04-19 | portfolio | `/auth/login` | `/api/auth/login` | Backend uses `prefix="/api"` |
| 2026-04-19 | portfolio | `/auth/register` | `/api/auth/register` | Backend uses `prefix="/api"` |
| 2026-04-19 | main | `getByRole('button', { name: '返回分析' })` | `.first()` | Two buttons exist (header + portfolio section) |
| 2026-04-19 | main | CSS variable `--color-up` | Check App.css via `/src/App.css` | CSS modules prevent getComputedStyle |
| 2026-04-19 | main | `getByText('预测')` | `.pred-title` | Disclaimer now also contains "预测" |
| 2026-04-19 | main | Disclaimer only in expanded panel | Always rendered | Bug fix: disclaimer now shows even when no model |

## Assertion Fixes (Healer memory)

| Date | Test | Old Assertion | New Assertion | Reason |
|------|------|-------------|-------------|--------|
| 2026-04-19 | auth error | "Invalid email or password" | "邮箱或密码错误" | Backend error messages in Chinese |

## Known App Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| 404 on `/api/predict/AAPL/forecast` | Expected | ML models only for BABA/TSLA/AAPL/NVDA/GLD. Frontend handles gracefully. |
| No A-share data in DB | Data gap | StockSelector has A-share sectors but DB only has US stocks from migration. Search via AKShare works but OHLC needs seeding. |
| bcrypt 5.0.0 incompatible with passlib 1.7.4 | Fixed | Downgraded to bcrypt 4.3.0 |

## Changelog

| Date | Change | By |
|------|--------|-----|
| 2026-04-19 | Initial exploration: routes, selectors, auth flow | E2E setup |
| 2026-04-19 | Fixed `/auth/*` → `/api/auth/*` in Portfolio.tsx | E2E setup |
| 2026-04-19 | Fixed auth error messages to Chinese | E2E setup |
| 2026-04-19 | Fixed bcrypt version incompatibility | E2E setup |
| 2026-04-19 | Added `/api` prefix to auth router in main.py | E2E setup |
| 2026-04-19 | Added 7.2.15/7.2.16 canvas particle click tests (31 tests total ✅) | E2E setup |
| 2026-04-19 | Fixed BasePage BASE_URL default: `localhost:3000` → `localhost:7777/PokieTicker` | E2E setup |

## Canvas Particle Testing

| Aspect | Value | Notes |
|--------|-------|-------|
| Canvas particle page coords | x: 50-90, y: 260-310 | Confirmed via pixel scan with getImageData |
| Headless DPR | 1 | devicePixelRatio=1 in headless Chromium, no scaling needed |
| Click position | `page.mouse.click(50, 275)` | Triggers onArticleSelect → SimilarDaysPanel |
| DPR-aware formula | `ctx.getImageData(cx * dpr, cy * dpr, 1, 1)` | Works for DPR=1 (headless) and DPR=2 (real browser) |

## SimilarDaysPanel Selectors

| Element | Selector | Notes |
|---------|----------|-------|
| Heading | `getByRole('heading', { name: '相似日' })` | |
| Close button | `button:has-text("关闭")` | SimilarDaysPanel uses `.range-clear-btn` |
| Stats section | `.sim-stats-card` | "历史规律" statistics |
| Period list | `.sim-day-card` | Each similar day entry |

---
