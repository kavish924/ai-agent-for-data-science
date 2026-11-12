"use client";

import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type ChartManifest,
  type ExecutionLog,
  type Plan,
  type Profile,
  type Session,
} from "@/lib/api/client";
import { PlanReview } from "./PlanReview";
import { ProfileScreen } from "./ProfileScreen";
import { DoneScreen, RunningScreen } from "./RunScreen";
import { ErrorNote, Shell, Spinner, type StepName } from "./Shell";
import { UploadScreen } from "./UploadScreen";

const POLL_MS = 800;
const EXECUTED = new Set(["executed", "modeled", "reported"]);

/** Which screen a session state belongs to (Spec 04 FR-RV-12). */
export function screenFor(session: Session | null): StepName {
  if (!session) return "Upload";
  if (session.state === "uploaded" || session.state === "profiled") return "Profile";
  if (session.state === "awaiting_approval" || session.state === "approved") return "Review plan";
  if (session.state === "executing") return "Run";
  return EXECUTED.has(session.state) ? "Download" : "Upload";
}

export function AgentFlow() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const sessionId = params.get("session");

  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [log, setLog] = useState<ExecutionLog | null>(null);
  const [charts, setCharts] = useState<ChartManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openSession = useCallback(
    (id: string | null) => router.replace(id ? `${pathname}?session=${id}` : pathname),
    [router, pathname],
  );

  // Load the session and whatever its current screen needs.
  const refresh = useCallback(async () => {
    if (!sessionId) {
      setSession(null);
      return;
    }
    try {
      const next = await api.session(sessionId);
      setSession(next);
      setError(null);
      const screen = screenFor(next);
      if (next.state !== "uploaded" && screen !== "Upload") setProfile(await api.profile(sessionId));
      if (screen === "Review plan") setPlan(await api.getPlan(sessionId));
      if (screen === "Download") {
        setLog(await api.executionLog(sessionId));
        // charts are optional: an old run (or a failed render) must not block the download
        setCharts(await api.charts(sessionId).catch(() => null));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this session.");
      if (err instanceof ApiError && err.status === 404) setSession(null);
    }
  }, [sessionId]);

  useEffect(() => {
    setPlan(null);
    setProfile(null);
    setLog(null);
    setCharts(null);
    void refresh();
  }, [refresh]);

  // Poll while background work runs (profiling, execution).
  const waiting = session && ((session.state === "uploaded" && !session.error) || session.state === "executing");
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, refresh]);

  const screen = screenFor(session);
  const key = `${screen}-${session?.state}-${session?.plan_version ?? 0}`;

  let body: React.ReactNode;
  if (!session) {
    body = <UploadScreen onUploaded={(created) => openSession(created.id)} />;
  } else if (session.state === "uploaded") {
    body = (
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-4 px-4">
        {session.error ? (
          <>
            <ErrorNote>{session.error}</ErrorNote>
            <button type="button" onClick={() => void api.retryProfiling(session.id).then(refresh)}
              className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-white hover:bg-accent-strong">
              Retry profiling
            </button>
          </>
        ) : (
          <Spinner label="Profiling your data: types, missing values, duplicates, outliers…" />
        )}
      </main>
    );
  } else if (screen === "Profile" && profile) {
    body = <ProfileScreen session={session} profile={profile} onPlanned={() => void refresh()} />;
  } else if (screen === "Review plan" && plan) {
    body =
      session.state === "approved" ? (
        <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
          <h1 className="font-display text-2xl font-semibold">Plan approved</h1>
          <p className="text-sm text-ink-soft">Version {session.plan_version} is approved and ready to run.</p>
          <button type="button" onClick={() => void api.execute(session.id).then(refresh)}
            className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-white hover:bg-accent-strong">
            Run approved plan
          </button>
        </main>
      ) : (
        <PlanReview
          sessionId={session.id}
          initialPlan={plan}
          profile={profile}
          initialError={session.failed_stage === "execute" ? session.error : null}
          onStarted={() => void refresh()}
        />
      );
  } else if (screen === "Run") {
    body = <RunningScreen />;
  } else if (screen === "Download" && log) {
    body = <DoneScreen session={session} log={log} charts={charts} />;
  } else {
    body = (
      <main className="flex flex-1 items-center justify-center">
        <Spinner label="Loading…" />
      </main>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <Shell current={screen} sessionId={session?.id} onReset={() => openSession(null)}>
        {error && (
          <div className="mx-auto w-full max-w-4xl px-4 pt-4">
            <ErrorNote>{error}</ErrorNote>
          </div>
        )}
        <AnimatePresence mode="wait">
          <motion.div
            key={key}
            className="flex flex-1 flex-col"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            {body}
          </motion.div>
        </AnimatePresence>
      </Shell>
    </MotionConfig>
  );
}
