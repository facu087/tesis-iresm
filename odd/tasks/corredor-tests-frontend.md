# Feature: corredor de tests del frontend

## Objective
Give the frontend an automated test runner and cover the two behaviors that every
native review of PRs #57–#63 flagged as untested: how `/analyzing` finishes and the
keyboard behavior of the `/report` tabs.

## Problem / why
The frontend has no test runner. Interactive behavior was checked in a headless
browser with scripts that are not in the repo (traspaso 4.10).

## Scope
- Vitest + React Testing Library + jsdom, following
  `frontend/node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md`.
- `npm test` script in `frontend/package.json`.
- Tests for `/analyzing` and the `/report` tab keyboard.
- Docs: test section in `.claude/CLAUDE.md`, traspaso 4.10 updated.

Out of scope: Playwright / end-to-end tests, CI workflow, other screens.

## Constraints
- No network: `fetch` and API calls are mocked; no backend needed.
- Timing tests use fake timers, never real sleeps.
- Test code and comments in English; existing UI strings stay as they are.
- Do not change production behavior; if a test exposes a bug, report it instead of fixing it silently.

## Tasks
- [x] T1 — Runner setup: dev deps, `vitest.config.mts`, setup file with jest-dom matchers, `npm test` script, `src/test/` helpers if needed, one smoke test. Route: delegated (writer, 2+ files).
- [x] T2 — `/analyzing` tests: response before the last step, response after the last step, backend error, network error (TypeError message), no case → `/analizar`. Route: delegated.
- [ ] T3 — `/report` tab keyboard tests: ArrowRight/ArrowLeft wrap, Home/End, Alt+Arrow ignored, aria-selected/tabIndex/focus move with selection. Route: delegated.
- [ ] T4 — Docs: `.claude/CLAUDE.md` (how to run frontend tests), `.claude/traspaso.md` 4.10 (runner exists; remove the three details fixed in PR #66). Route: delegated.

## Acceptance criteria
- `npm test` in `frontend/` runs and passes, deterministically, offline.
- `npm run build`, `npx tsc --noEmit` and `npm run lint` still pass.

## Delivery
Strategy: ask-on-risk. Forecast ~400 authored lines (lockfile excluded).

## Progress
(updated per task with commit hash and checks)

- T1 — done. Vitest 4.1 (not 5: vitest 5 needs `@types/node` >= 22 and the repo pins ^20),
  RTL 16, user-event 14, jest-dom 7, jsdom 29, @vitejs/plugin-react 6. The `@/` alias uses
  Vite's native `resolve.tsconfigPaths` instead of the guide's vite-tsconfig-paths plugin
  (Vite warns the plugin is redundant). Tests live next to the code as `src/**/*.test.tsx`.
  Checks: `npm test` 1/1 pass; `npx tsc --noEmit` exit 0; `npm run lint` clean;
  `npm run build` ok. `npm audit` reports 12 findings, all pre-existing (next, eslint-config-next).
  Commit: 9908047.

- T2 — done. `src/app/analyzing/page.test.tsx` (6 cases, fake timers, mocked router and API;
  shared fixture in `src/test/fixtures.ts`): early response waits for the catch-up and
  navigates at 1500 + 7×350 ms; late response navigates right after it resolves (last step
  held "Paso 8 de 8"); file input uses analyzeFile; backend Error message shown, no
  navigation even after all timers; TypeError shows the readable network message, never
  "Failed to fetch"; no case → replace("/analizar"). No bug found.
  Checks: `npm test` 7/7 pass; `npx tsc --noEmit` exit 0; `npm run lint` clean.
  Commit: see git log (`test(s4): cierre de la vista de progreso del análisis`).

## Next step
T3.
