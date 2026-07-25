# ADR-020 — Frontend UI Component & Animation Library Stack

## Status

Accepted

## Context

The frontend scaffold (#10, 2026-07-12) shipped with plain Tailwind CSS only
— `shadcn/ui` was already earmarked in the TRD's frontend stack table but
explicitly deferred ("until a feature screen needs it", per
`.ai/memory/project-memory.md`). By Sprint 2 #36, the app had its first real
screens (login, dashboard, dataset upload/list), and CLAUDE.md's Domain &
Portfolio Requirements are explicit that this project must read as senior,
recruiter-legible, "premium" engineering output — not tutorial-tier styling.
Hand-rolling animation/motion CSS per component, or building a design system
from scratch, does not clear that bar efficiently for a single-developer
portfolio project.

## Decision

Adopt a curated set of React-compatible UI/animation libraries, all
distributed via the shadcn/ui CLI model — components are copied into
`frontend/src/components/` and owned/edited in-repo, not pulled in as opaque
npm dependencies:

- **shadcn/ui** — the foundation: `components.json`, base primitives
  (`Button`, `Input`, `Label`, `Card`, `Badge`, `Skeleton`, `Separator`), and
  the oklch-based CSS custom-property design-token system in `index.css`
  (`@theme inline`, light/dark tokens).
- **Animate UI** (animate-ui.dev) — general animated interactive components
  (tabs, tooltips), built on Motion.
- **Aceternity UI** (ui.aceternity.com) — high-impact visual moments (login
  page background beams, spotlight, text-generate-effect). Substituted for
  the originally-requested `inspira-ui` (github.com/unovue/inspira-ui),
  which is Vue/Nuxt-only and incompatible with this repo's React 19 stack
  (ADR-002). Aceternity UI is React + Tailwind + Motion, and is the library
  inspira-ui itself is modeled on — a like-for-like visual-style swap, not a
  downgrade.
- **Lenis** (github.com/darkroomengineering/lenis) — smooth scroll, wired
  into `AppLayout`'s `<main>` region via a `useLenis` hook.
- **Motion** (the renamed Framer Motion, `motion` npm package) — the shared
  animation primitive underneath Animate UI, Aceternity UI, and
  hand-written transitions (list enter/exit, sidebar active-state
  indicator, page transitions).

This choice is also captured as a project skill
(`.claude/skills/frontend-animation-libs/SKILL.md`) so future frontend work
in this repo defaults to these libraries instead of hand-rolled animation.

## Alternatives Considered

- **inspira-ui as originally requested** — rejected: Vue/Nuxt-only, would
  require either a second frontend framework or a from-scratch React port
  of every component. Not compatible with ADR-002 (React).
- **Magic UI** — considered as an alternative inspira-ui substitute;
  Aceternity UI chosen instead as the more direct stylistic ancestor of
  inspira-ui, with broader component coverage for the login/marketing-style
  surfaces this project needs.
- **Hand-rolled CSS animation / Motion only, no component libraries** —
  rejected: slower to reach a "premium" visual bar and inconsistent across
  screens. The shadcn CLI model keeps components in-repo and editable,
  avoiding a black-box npm dependency while still giving a real starting
  point.
- **Full design-system rebuild via the `ui-ux-pro-max`/`frontend-design`
  skills from scratch** — rejected as redundant; those skills' guidance
  (styles, palettes, UX checklists) is used as a review layer over these
  libraries' output, not a replacement build.

## Consequences

### Positive

- Components are copied into the repo (shadcn CLI model), not opaque npm
  dependencies — fully editable and auditable, consistent with the
  project's stance against black-box shortcuts around data handling.
- One consistent oklch-based design-token system (`index.css`) now backs
  light/dark theming across all screens, replacing ad hoc per-page Tailwind
  classes.
- Motion is the single shared animation primitive (Animate UI, Aceternity
  UI, and hand-written transitions all build on it) — no competing
  animation-library sprawl.
- Login/Dashboard/Datasets screens now meet the "premium, recruiter-legible"
  bar the portfolio requires, ahead of the clinical-analytics/SHAP pillars
  where visual polish matters even more.

### Negative

- New dependency surface in `frontend/package.json`: `motion`, `lenis`,
  `class-variance-authority`, `clsx`, `tailwind-merge`, `@base-ui/react`,
  `@floating-ui/react`, `lucide-react`, `@fontsource-variable/geist`, and
  the `shadcn` CLI itself — nine new packages, all MIT/permissive-licensed,
  but real ongoing surface to keep patched.
- shadcn/Aceternity/Animate UI components are copy-pasted, not versioned
  npm packages — picking up upstream fixes is a manual re-copy, not
  `npm update`.
- Explainability screens (SHAP force/dependency plots, validation reports)
  must keep motion subtle per the skill's own boundary note — a discipline
  burden enforced by code review, not tooling.
- Lenis is wired but not yet load-bearing — no current page overflows
  enough to need smooth scroll. Revisit if it's still unused once the
  clinical analytics dashboard (Pillar 3) ships.

## References

- ADR-002 — React as Frontend Framework
- `.claude/skills/frontend-animation-libs/SKILL.md`
- PR #55 (skill added), PR #56 (`feat(frontend): integrate Shadcn and
  Aceternity UI animations`)
- `docs/02_TRD.md` §6 Frontend Architecture
