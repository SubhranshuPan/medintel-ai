import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50 text-slate-900">
      <h1 className="text-3xl font-semibold">404</h1>
      <p className="text-sm text-slate-500">This clinical pathway does not exist.</p>
      <Link to="/dashboard" className="text-sm font-medium text-teal-700 hover:underline">
        Return to dashboard
      </Link>
    </div>
  );
}
