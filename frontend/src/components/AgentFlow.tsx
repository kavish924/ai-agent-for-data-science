"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type ChartManifest,
  type ExecutionLog,
  type ModelRuns,
  type Plan,
  type Profile,
  type Session,
  type TargetSuggestion,
} from "@/lib/api/client";
import { PlanReview } from "./PlanReview";
import { ProfileScreen } from "./ProfileScreen";
import { DoneScreen, RunningScreen } from "./RunScreen";
import { ErrorState } from "./ErrorState";
import { readTab, type ResultTab } from "./ResultsTabs";
import { ErrorNote, Shell, Spinner, STEPS, type StepName } from "./Shell";
import { useScreenFocus } from "./useScreenFocus";
import { UploadScreen } from "./UploadScreen";

const POLL_MS = 800;
const ANNOUNCE: Record<StepName, string> = {
  Upload: "Upload a CSV to start",
  Profile: "Profile",
  "Review plan": "Review the cleaning plan",
  Run: "Running the approved plan",
  Download: "Results ready",
};
const EXECUTED = new Set(["executed", "modeling", "modeled", "reported"]);

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
  const tab = readTab(params);

  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [log, setLog] = useState<ExecutionLog | null>(null);
  const [charts, setCharts] = useState<ChartManifest | null>(null);
  const [runs, setRuns] = useState<ModelRuns | null>(null);
  const [suggestions, setSuggestions] = useState<TargetSuggestion[]>([]);
  const [reportSource, setReportSource] = useState<"llm" | "template" | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // FR-RV-20: problems that get their own screen or banner with a next step
  const [problem, setProblem] = useState<"missing" | "network" | null>(null);

  const openSession = useCallback(
    (id: string | null) => router.replace(id ? `${pathname}?session=${id}` : pathname),
    [router, pathname],
  );
  const selectTab = useCallback(
    (next: ResultTab) => {
      if (!sessionId) return;
      router.replace(`${pathname}?session=${sessionId}${next === "overview" ? "" : `&tab=${next}`}`, { scroll: false });
    },
    [router, pathname, sessionId],
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
      setProblem(null);
      const screen = screenFor(next);
      if (next.state !== "uploaded" && screen !== "Upload") {
        setProfile(await api.profile(sessionId));
        setSuggestions(await api.targets(sessionId).catch(() => []));
      }
      if (screen === "Review plan") setPlan(await api.getPlan(sessionId));
      if (screen === "Download") {
        setLog(await api.executionLog(sessionId));
        // charts are optional: an old run (or a failed render) must not block the download
        setCharts(await api.charts(sessionId).catch(() => null));
        // model runs exist only after training; a 404 simply means "not trained yet"
        setRuns(await api.modelRuns(sessionId).catch(() => null));
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404 && err.code === "session_not_found") {
        setSession(null);
        setProblem("missing");
      } else if (err instanceof ApiError && err.status === 0) {
        setProblem("network");
      } else {
        setError(err instanceof ApiError ? err.message : "Couldn't load this session.");
      }
    }
  }, [sessionId]);

  useEffect(() => {
    setPlan(null);
    setProfile(null);
    setLog(null);
    setCharts(null);
    setRuns(null);
    setReportSource(null);
    void refresh();
  }, [refresh]);

  // Poll while background work runs (profiling, execution).
  const waiting =
    session &&
    ((session.state === "uploaded" && !session.error) ||
      session.state === "executing" ||
      session.state === "modeling");
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, refresh]);

  const screen = screenFor(session);
  const focusKey = problem === "missing" ? "missing" : screen;
  const step = STEPS.indexOf(screen) + 1;
  const { announcement, focus } = useScreenFocus(
    focusKey,
    problem === "missing" ? "This analysis isn't available" : `Step ${step} of ${STEPS.length}: ${ANNOUNCE[screen]}`,
    { immediate: false },
  );
  // The Download screen stays mounted while training moves executed -> modeling -> modeled
  const key = `${screen}-${screen === "Download" ? "" : session?.state}-${session?.plan_version ?? 0}`;

  let body: React.ReactNode;
  if (problem === "missing") {
    body = (
      <ErrorState
        kind="missing"
        onStartOver={() => {
          setProblem(null);
          openSession(null);
        }}
        onRetry={() => void refresh()}
      />
    );
  } else if (!session) {
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
          <>
            <h1 className="font-display text-2xl font-semibold">Profiling your data</h1>
            <Spinner label="Checking types, missing values, duplicates and outliers…" />
          </>
        )}
      </main>
    );
  } else if (screen === "Profile" && profile) {
    body = (
      <ProfileScreen session={session} profile={profile} suggestions={suggestions}
        onPlanned={() => void refresh()} />
    );
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
    body = (
      <DoneScreen
        tab={tab}
        onTab={selectTab}
        session={session}
        log={log}
        charts={charts}
        runs={runs}
        suggestions={suggestions}
        report={{
          source: reportSource,
          busy: reportBusy,
          onCreate: (renarrate) => {
            setReportBusy(true);
            setError(null);
            void api
              .createReport(session.id, renarrate)
              .then((created) => setReportSource(created.narration_source))
              .catch((err: unknown) =>
                setError(err instanceof ApiError ? err.message : "Couldn't create the report."),
              )
              .finally(() => {
                setReportBusy(false);
                void refresh();
              });
          },
        }}
        onTrain={(target) =>
          void api.train(session.id, target).then(refresh, (err: unknown) =>
            setError(err instanceof ApiError ? err.message : "Couldn't start training."),
          )
        }
      />
    );
  } else {
    body = (
      <main className="flex flex-1 items-center justify-center">
        <Spinner label="Loading…" />
      </main>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <Shell current={screen} sessionId={session?.id} onReset={() => openSession(null)} announcement={announcement}>
        {problem === "network" && (
          <div className="px-4">
            <ErrorState kind="network" onStartOver={() => openSession(null)} onRetry={() => void refresh()} />
          </div>
        )}
        {error && (
          <div className="mx-auto w-full max-w-4xl px-4 pt-4">
            <ErrorNote>{error}</ErrorNote>
          </div>
        )}
        <AnimatePresence mode="wait">
          <motion.div
            key={problem === "missing" ? "missing" : key}
            className="flex flex-1 flex-col"
            onAnimationComplete={focus}
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
