---
name: frontend-animation-libs
description: Use for any frontend work on the MedIntel AI React app (frontend/) — component polish, page transitions, scroll behavior, dashboard/chart interactions. Documents which of the three approved third-party UI libraries (Animate UI, Lenis, Aceternity UI) to reach for and how they fit this repo's stack (React 19 + Vite + Tailwind v4, no shadcn/ui scaffolded yet).
---

# Frontend animation/UI libraries for MedIntel AI

This repo's frontend (`frontend/`) is React 19 + Vite + Tailwind CSS v4 (ADR-002).
No `framer-motion`/`motion`, no shadcn/ui `components.json`, no path alias (`@/*`) exist yet — check before assuming any of this is wired up.

Three libraries are approved for frontend work here. Reach for one of these before hand-rolling animation, scroll, or a component that already exists in one of them — per `ponytail`, check the ladder (native CSS/Tailwind first, then these) before writing custom motion code.

## 1. Animate UI — general animated components
- Repo: https://github.com/imskyleen/animate-ui
- React + TypeScript + Tailwind CSS + Motion (Framer Motion), distributed shadcn/ui-CLI style — copy components into the repo, not an npm dependency.
- Use for: buttons, badges, list-item enter/exit transitions, tabs, dialogs, tooltips — anything in `DatasetsPage.tsx`, `AppLayout.tsx` nav, dashboard cards that needs polish beyond plain Tailwind.
- Requires shadcn/ui `init` + `motion` installed first (see setup below) — components are added one at a time via CLI, then owned/edited in-repo like any other component.

## 2. Lenis — smooth scroll
- Repo: https://github.com/darkroomengineering/lenis
- Framework-agnostic; npm package `lenis`, with a React-friendly usage pattern (no separate `lenis/react` package needed for a simple setup — instantiate in a top-level effect).
- Use for: the scrollable `<main>` region in `AppLayout.tsx` once the clinical dashboard / patient cohort pages have enough content to scroll — smooths native scroll, useful alongside scroll-triggered chart reveals on the analytics dashboard pillar.
- Don't add until a page actually overflows — this is pure UX polish, not needed for the current short dataset list.

## 3. Aceternity UI — animated hero/marketing-style components
- Site: https://ui.aceternity.com/
- Approved as the React-compatible swap for `inspira-ui` (Vue/Nuxt-only — confirmed incompatible with this React stack, do not use inspira-ui directly).
- React + Tailwind + Motion, shadcn/ui-CLI style distribution (same install pattern as Animate UI — components fetched via `shadcn` CLI from Aceternity's registry URL, then owned in-repo).
- Use for: higher-impact visual moments — login page background/hero treatment, empty-states, landing/marketing-style sections if the portfolio ever gets a public-facing marketing page. Lower priority than Animate UI/Lenis for the current dashboard-heavy pages.

## Setup prerequisite (not done yet — do once, before first component add)
1. Add path alias: `"@/*": ["./src/*"]` in `frontend/tsconfig.json` `compilerOptions.paths`, and a matching `resolve.alias` in `frontend/vite.config.ts`.
2. `npx shadcn@latest init` from `frontend/` — creates `components.json`, picks Tailwind v4 config.
3. `npm i motion` (Animate UI and Aceternity UI both animate via Motion, the renamed Framer Motion package).
4. Only then: `npx shadcn@latest add <component-registry-url>` per component, from Animate UI's or Aceternity's docs.

## Boundaries
- These are additive polish libraries, not a stack change — ADR-002 (React) stands. Don't propose replacing Tailwind or the routing/data-fetching approach in `frontend/src/lib/api.ts`.
- Explainability/clinical UI (SHAP charts, validation reports) prioritizes clarity over animation — keep motion subtle (fades/slides), never obscure or delay medically relevant data.
