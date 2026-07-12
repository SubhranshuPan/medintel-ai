# MedIntel AI — Frontend

React 19 + TypeScript single-page app for the MedIntel AI clinical intelligence
platform (ADR-002). Build tooling: Vite. Styling: Tailwind CSS v4. Routing:
React Router.

## Requirements
- Node.js 20+
- The MedIntel backend running (see `../backend/README.md`)

## Quickstart
```bash
npm install
cp .env.example .env      # point VITE_API_BASE_URL at the backend
npm run dev
```
App: http://localhost:5173 — proxies nothing; the client calls the backend at
`VITE_API_BASE_URL` + `/api/v1` directly (CORS handled server-side).

## Scripts
```bash
npm run dev        # Vite dev server (HMR)
npm run build      # type-check (tsc --noEmit) + production build
npm run preview    # serve the production build locally
```

## Layout
```
src/
  main.tsx              # app entry: React root + <BrowserRouter>
  App.tsx              # route table
  index.css            # Tailwind entry
  components/
    AppLayout.tsx      # sidebar + header shell (<Outlet/>)
  pages/
    DashboardPage.tsx  # Pillar 2 placeholder; live backend health probe
    PatientsPage.tsx   # Pillar 1 placeholder
    NotFoundPage.tsx
  lib/
    api.ts             # typed fetch client (getHealth, ApiError)
```

## Planned (subsequent sprints)
- Data layer: TanStack Query once real fetching screens land
- Zustand (client state), React Hook Form + Zod (forms), Recharts (analytics)
- shadcn/ui component primitives
- Auth wiring against `/api/v1/auth` (JWT from the backend auth module)
