import { type SubmitEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  type Dataset,
  type DatasetVersion,
  getDataset,
  getToken,
  listDatasets,
  uploadDataset,
} from "../lib/api";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // mirrors the backend cap; server stays authoritative

const STATUS_STYLES: Record<DatasetVersion["validation_status"], string> = {
  passed: "border-green-200 bg-green-50 text-green-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  pending: "border-slate-200 bg-slate-100 text-slate-600",
};

/** Badge text carries the meaning on its own — color is reinforcement, not the only signal. */
function StatusBadge({ status }: { status: DatasetVersion["validation_status"] }) {
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
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
    <div className="mt-1 text-xs text-red-700">
      <ul className="list-inside list-disc space-y-0.5">
        {shown.map((f, i) => (
          <li key={i}>{explainFailure(f)}</li>
        ))}
      </ul>
      {(report.failure_count > shown.length || report.truncated) && (
        <details className="mt-1">
          <summary className="cursor-pointer text-slate-500">
            {report.failure_count} failure(s) total — raw report
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-50 p-2">
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

  if (error) return <p className="px-4 py-2 text-sm text-red-700">{error}</p>;
  if (!versions) return <p className="px-4 py-2 text-sm text-slate-400">Loading version history…</p>;

  return (
    <ul className="divide-y divide-slate-100 border-t border-slate-100 bg-slate-50 px-4">
      {versions.map((v) => (
        <li key={v.id} className="py-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-700">v{v.version_number}</span>
            <span className="text-slate-400">({v.origin})</span>
            <StatusBadge status={v.validation_status} />
            <span className="text-slate-400">{v.row_count ?? "?"} rows</span>
          </div>
          <ValidationReportDetail version={v} />
        </li>
      ))}
    </ul>
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
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="space-y-1">
        <label htmlFor="dataset-name" className="text-sm font-medium text-slate-700">
          Dataset name
        </label>
        <input
          id="dataset-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="block rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="dataset-file" className="text-sm font-medium text-slate-700">
          CSV file
        </label>
        <input
          id="dataset-file"
          type="file"
          accept=".csv,text/csv"
          required
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block text-sm text-slate-600"
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="cursor-pointer rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Uploading…" : "Upload"}
      </button>

      {error && (
        <p role="alert" className="w-full text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  );
}

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
        <h2 className="text-xl font-semibold text-slate-900">Datasets</h2>
        <p className="text-sm text-slate-500">
          <Link to="/login" className="text-teal-700 underline">
            Log in
          </Link>{" "}
          to upload and view datasets.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold text-slate-900">Datasets</h2>

      <UploadForm onUploaded={(d) => setDatasets((prev) => (prev ? [d, ...prev] : [d]))} />

      {error && (
        <p role="alert" className="flex items-center gap-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
          <button type="button" onClick={load} className="cursor-pointer underline">
            Retry
          </button>
        </p>
      )}

      {!datasets && !error && <p className="text-sm text-slate-400">Loading datasets…</p>}

      {datasets && datasets.length === 0 && (
        <p className="text-sm text-slate-500">No datasets yet — upload a CSV above.</p>
      )}

      {datasets && datasets.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
          {datasets.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => setExpanded((cur) => (cur === d.id ? null : d.id))}
                className="flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">{d.name}</p>
                  <p className="text-xs text-slate-400">{new Date(d.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  {d.latest_version && (
                    <>
                      <span className="text-xs text-slate-400">
                        v{d.latest_version.version_number} · {d.latest_version.row_count ?? "?"} rows
                      </span>
                      <StatusBadge status={d.latest_version.validation_status} />
                    </>
                  )}
                </div>
              </button>
              {expanded === d.id && <VersionHistory datasetId={d.id} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
