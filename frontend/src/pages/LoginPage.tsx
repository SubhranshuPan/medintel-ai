import { type SubmitEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";

import { ApiError, login, setToken } from "@/lib/api";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { Spotlight } from "@/components/ui/spotlight";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

/**
 * No login screen exists anywhere in the app yet (#10 scoped the frontend
 * scaffold to a health-check placeholder). #36 requires "auth token
 * attached" and "upload works end-to-end" — neither is possible without a
 * way to obtain a token, so this is the minimum enabler, not scope creep.
 * Registration stays out of scope; use the API/Swagger UI to create a user.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      navigate("/datasets", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-neutral-950">
      {/* Aceternity effects */}
      <Spotlight className="-top-40 left-0 md:-top-20 md:left-60" fill="rgba(20, 184, 166, 0.35)" />
      <BackgroundBeams className="opacity-40" />

      {/* Left branding panel (hidden on mobile) */}
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="relative z-10 hidden w-1/2 flex-col items-center justify-center px-16 lg:flex"
      >
        <div className="max-w-md space-y-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/20 ring-1 ring-teal-500/30">
              <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-2xl font-bold tracking-tight text-white">
              MedIntel<span className="text-teal-400"> AI</span>
            </span>
          </div>
          <TextGenerateEffect
            words="Clinical Intelligence Platform for Modern Healthcare"
            className="!text-neutral-300"
            duration={0.4}
          />
          <p className="text-sm leading-relaxed text-neutral-500">
            Readmission risk prediction · SHAP explainability · Patient cohort
            analytics · Powered by synthetic data under GDPR-aware design.
          </p>
        </div>
      </motion.div>

      {/* Login card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="relative z-10 w-full max-w-md px-6 lg:w-1/2 lg:px-16"
      >
        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-2xl border border-white/10 bg-neutral-900/70 p-8 shadow-2xl shadow-teal-500/5 backdrop-blur-xl"
        >
          {/* Mobile logo */}
          <div className="mb-2 lg:hidden">
            <span className="text-xl font-bold tracking-tight text-white">
              MedIntel<span className="text-teal-400"> AI</span>
            </span>
          </div>

          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-white">Sign in</h2>
            <p className="text-sm text-neutral-500">
              Access the clinical intelligence dashboard
            </p>
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              role="alert"
              className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400"
            >
              {error}
            </motion.p>
          )}

          <div className="space-y-2">
            <Label htmlFor="email" className="text-neutral-300">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              required
              placeholder="clinician@nhs.uk"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-white/10 bg-white/5 text-white placeholder:text-neutral-600 focus:border-teal-500 focus:ring-teal-500/30"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password" className="text-neutral-300">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-white/10 bg-white/5 text-white placeholder:text-neutral-600 focus:border-teal-500 focus:ring-teal-500/30"
            />
          </div>

          <Button
            type="submit"
            disabled={submitting}
            className="w-full bg-teal-600 text-white hover:bg-teal-500 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </Button>

          <p className="text-center text-xs text-neutral-600">
            Synthetic data · GDPR-aware design · NICE-aligned
          </p>
        </form>
      </motion.div>
    </div>
  );
}
