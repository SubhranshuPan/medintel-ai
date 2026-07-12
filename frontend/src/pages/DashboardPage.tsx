import { useEffect, useState } from "react";

import { getHealth, type HealthStatus } from "../lib/api";

type BackendState =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthStatus }
  | { kind: "error"; message: string };

/**
 * Placeholder dashboard. Proves the API client reaches the backend by rendering
 * the live health probe; real analytics widgets (Pillar 2) replace the cards.
 */
export function DashboardPage() {
  const [backend, setBackend] = useState<BackendState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((health) => {
        if (active) setBackend({ kind: "ok", health });
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (active) setBackend({ kind: "error", message });
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Clinical Dashboard</h2>
        <p className="text-sm text-slate-500">
          Readmission risk and cohort analytics land here in Pillar 2.
        </p>
      </div>

      <BackendStatusCard backend={backend} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Active cohorts" value="—" />
        <MetricCard label="High-risk patients" value="—" />
        <MetricCard label="Avg. readmission risk" value="—" />
      </div>
    </section>
  );
}

function BackendStatusCard({ backend }: { backend: BackendState }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700">Backend API</span>
        <StatusBadge backend={backend} />
      </div>
      {backend.kind === "ok" && (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
          <div>Version: {backend.health.version}</div>
          <div>Environment: {backend.health.environment}</div>
        </dl>
      )}
      {backend.kind === "error" && (
        <p className="mt-3 text-xs text-red-600">{backend.message}</p>
      )}
    </div>
  );
}

function StatusBadge({ backend }: { backend: BackendState }) {
  const styles: Record<BackendState["kind"], string> = {
    loading: "bg-slate-100 text-slate-500",
    ok: "bg-teal-50 text-teal-700",
    error: "bg-red-50 text-red-700",
  };
  const label = { loading: "Checking…", ok: "Connected", error: "Unreachable" }[
    backend.kind
  ];
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[backend.kind]}`}>
      {label}
    </span>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
