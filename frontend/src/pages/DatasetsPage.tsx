import { type SubmitEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";

import {
  ApiError,
  type Dataset,
  type DatasetVersion,
  getDataset,
  getToken,
  listDatasets,
  uploadDataset,
} from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // mirrors the backend cap; server stays authoritative

const STATUS_VARIANT: Record<DatasetVersion["validation_status"], "default" | "secondary" | "destructive"> = {
  passed: "default",
  failed: "destructive",
  pending: "secondary",
};

/** Badge text carries the meaning on its own — color is reinforcement, not the only signal. */
function StatusBadge({ status }: { status: DatasetVersion["validation_status"] }) {
  return <Badge variant={STATUS_VARIANT[status]}>{status}</Badge>;
}

function explainFailure(failure: Record<string, unknown>): string {
  const column = typeof failure.column === "string" ? failure.column : undefined;
  const check = typeof failure.check === "string" ? failure.check : undefined;
  if (column && check) return `Column "${column}" failed check: ${check}`;
  if (check) return check;
  return JSON.stringify(failure);
}

function ValidationReportDetail({ version }: { version: DatasetVersion }) {
  const report = version.validation_report;
  if (!report || report.failure_count === 0) return null;
  const shown = report.failures.slice(0, 5);
  return (
    <div className="mt-2 text-xs text-destructive">
      <ul className="list-inside list-disc space-y-0.5">
        {shown.map((f, i) => (
          <li key={i}>{explainFailure(f)}</li>
        ))}
      </ul>
      {(report.failure_count > shown.length || report.truncated) && (
        <details className="mt-1">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            {report.failure_count} failure(s) total — raw report
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-muted p-2 text-xs">
            {JSON.stringify(report.failures, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function VersionHistory({ datasetId }: { datasetId: string }) {
  const [versions, setVersions] = useState<DatasetVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDataset(datasetId)
      .then((detail) => {
        if (!cancelled) setVersions(detail.versions);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail ?? err.message : "Failed to load");
      });
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  if (error) return <p className="px-4 py-3 text-sm text-destructive">{error}</p>;
  if (!versions)
    return (
      <div className="space-y-2 px-4 py-3">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-36" />
      </div>
    );

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="overflow-hidden"
    >
      <Separator />
      <div className="bg-muted/30 px-4 py-3 space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Version History
        </p>
        <ul className="space-y-2">
          {versions.map((v) => (
            <motion.li
              key={v.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="rounded-lg border bg-card p-3 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-foreground">v{v.version_number}</span>
                <Badge variant="outline" className="text-xs">{v.origin}</Badge>
                <StatusBadge status={v.validation_status} />
                <span className="text-muted-foreground">{v.row_count ?? "?"} rows</span>
              </div>
              <ValidationReportDetail version={v} />
            </motion.li>
          ))}
        </ul>
      </div>
    </motion.div>
  );
}

function UploadForm({ onUploaded }: { onUploaded: (dataset: Dataset) => void }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget; // captured now — currentTarget nulls out after this handler returns
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Only .csv files are accepted");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("File exceeds the 50 MB upload limit");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const dataset = await uploadDataset(name, file);
      onUploaded(dataset);
      setName("");
      setFile(null);
      form.reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Dataset</CardTitle>
        <CardDescription>CSV files up to 50 MB · auto-validated on upload</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="dataset-name">Dataset name</Label>
            <Input
              id="dataset-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Heart Failure Cohort"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="dataset-file">CSV file</Label>
            <Input
              id="dataset-file"
              type="file"
              accept=".csv,text/csv"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <Button type="submit" disabled={submitting}>
            {submitting ? "Uploading…" : "Upload"}
          </Button>

          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                role="alert"
                className="w-full rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>
        </form>
      </CardContent>
    </Card>
  );
}

const listItem = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
};

export function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  function load() {
    setError(null);
    setDatasets(null);
    listDatasets()
      .then(setDatasets)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.detail ?? err.message : "Failed to load datasets");
      });
  }

  useEffect(() => {
    if (getToken()) load();
  }, []);

  if (!getToken()) {
    return (
      <section className="space-y-2">
        <h2 className="text-xl font-semibold text-foreground">Datasets</h2>
        <p className="text-sm text-muted-foreground">
          <Link to="/login" className="text-primary underline underline-offset-4 hover:text-primary/80">
            Log in
          </Link>{" "}
          to upload and view datasets.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Datasets</h2>
        <p className="text-sm text-muted-foreground">
          Manage clinical datasets for model training and validation.
        </p>
      </div>

      <UploadForm onUploaded={(d) => setDatasets((prev) => (prev ? [d, ...prev] : [d]))} />

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            {error}
            <Button variant="ghost" size="sm" onClick={load}>
              Retry
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {!datasets && !error && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      )}

      {datasets && datasets.length === 0 && (
        <Card className="flex items-center justify-center py-12 text-center">
          <CardContent>
            <p className="text-muted-foreground">No datasets yet — upload a CSV above.</p>
          </CardContent>
        </Card>
      )}

      {datasets && datasets.length > 0 && (
        <motion.div
          initial="hidden"
          animate="show"
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } }}
          className="space-y-3"
        >
          {datasets.map((d) => (
            <motion.div key={d.id} variants={listItem}>
              <Card className="overflow-hidden transition-shadow hover:shadow-md">
                <button
                  type="button"
                  onClick={() => setExpanded((cur) => (cur === d.id ? null : d.id))}
                  className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left"
                >
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-foreground">{d.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(d.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {d.latest_version && (
                      <>
                        <span className="text-xs text-muted-foreground">
                          v{d.latest_version.version_number} · {d.latest_version.row_count ?? "?"} rows
                        </span>
                        <StatusBadge status={d.latest_version.validation_status} />
                      </>
                    )}
                    <motion.svg
                      animate={{ rotate: expanded === d.id ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                      className="h-4 w-4 text-muted-foreground"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </motion.svg>
                  </div>
                </button>
                <AnimatePresence>
                  {expanded === d.id && <VersionHistory datasetId={d.id} />}
                </AnimatePresence>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      )}
    </section>
  );
}
