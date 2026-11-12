"use client";

import { api, type Session } from "@/lib/api/client";
import { ReportPanel } from "./ReportPanel";

/**
 * The Report tab (Spec 04 FR-RV-18): the report inside the app in a sandboxed frame
 * (no scripts, forms, popups or navigation), or an empty state that explains what a
 * report contains and offers to create one.
 */
export function ReportView({
  session,
  source,
  busy,
  onCreate,
}: {
  session: Session;
  source: "llm" | "template" | null;
  busy: boolean;
  onCreate: (renarrate: boolean) => void;
}) {
  const ready = session.state === "reported" && !busy;
  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div className="lg:w-72 lg:shrink-0">
        <ReportPanel session={session} source={source} busy={busy} onCreate={onCreate} />
      </div>
      {ready ? (
        <iframe
          src={api.reportUrl(session.id)}
          // No scripts, forms, popups or navigation. Same-origin only: some embedded
          // browsers (the Claude app's) block fully opaque-origin frames outright.
          sandbox="allow-same-origin"
          title={`Process report for ${session.original_filename}`}
          className="h-[75vh] min-h-[480px] w-full min-w-0 flex-1 rounded-xl border border-line bg-white"
        />
      ) : (
        <div className="flex min-h-64 flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong p-8 text-center">
          <p className="font-display text-lg font-semibold">No report yet</p>
          <p className="max-w-md text-sm leading-relaxed text-ink-soft">
            The report collects everything from this run in one file you can keep or share: the
            snapshot, every step and why, before vs after, charts, models and a written summary.
          </p>
        </div>
      )}
    </div>
  );
}
