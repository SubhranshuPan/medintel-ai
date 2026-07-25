import { useEffect, useState } from "react";
import { motion } from "motion/react";

import { getHealth, type HealthStatus } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

type BackendState =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthStatus }
  | { kind: "error"; message: string };

const PILLAR_METRICS = [
  {
    label: "Active Cohorts",
    value: "—",
    desc: "Patient cohort groups",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
      </svg>
    ),
  },
  {
    label: "High-Risk Patients",
    value: "—",
    desc: "Readmission risk > 70%",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  {
    label: "Avg. Readmission Risk",
    value: "—",
    desc: "Across all cohorts",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
] as const;

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
} as const;

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } },
};

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
    <motion.section
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={item}>
        <h2 className="text-xl font-semibold text-foreground">Clinical Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Readmission risk and cohort analytics land here in Pillar 2.
        </p>
      </motion.div>

      {/* Backend status card */}
      <motion.div variants={item}>
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Backend API</CardTitle>
              <CardDescription>FastAPI health probe status</CardDescription>
            </div>
            <BackendBadge backend={backend} />
          </CardHeader>
          {backend.kind === "ok" && (
            <CardContent>
              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <span>
                  Version: <span className="font-medium text-foreground">{backend.health.version}</span>
                </span>
                <Separator orientation="vertical" className="h-4" />
                <span>
                  Environment: <span className="font-medium text-foreground">{backend.health.environment}</span>
                </span>
              </div>
            </CardContent>
          )}
          {backend.kind === "error" && (
            <CardContent>
              <p className="text-sm text-destructive">{backend.message}</p>
            </CardContent>
          )}
          {backend.kind === "loading" && (
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-32" />
            </CardContent>
          )}
        </Card>
      </motion.div>

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PILLAR_METRICS.map((metric) => (
          <motion.div key={metric.label} variants={item}>
            <Card className="group transition-shadow hover:shadow-md">
              <CardHeader className="flex-row items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                  {metric.icon}
                </div>
                <div>
                  <CardDescription className="text-xs uppercase tracking-wide">
                    {metric.label}
                  </CardDescription>
                  <CardTitle className="text-2xl">{metric.value}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{metric.desc}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}

function BackendBadge({ backend }: { backend: BackendState }) {
  const map: Record<BackendState["kind"], { label: string; variant: "default" | "secondary" | "destructive" }> = {
    loading: { label: "Checking…", variant: "secondary" },
    ok: { label: "Connected", variant: "default" },
    error: { label: "Unreachable", variant: "destructive" },
  };
  const { label, variant } = map[backend.kind];
  return <Badge variant={variant}>{label}</Badge>;
}
