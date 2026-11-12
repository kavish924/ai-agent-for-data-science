"use client";

import { motion } from "framer-motion";

export const STEPS = ["Upload", "Profile", "Review plan", "Run", "Download"] as const;
export type StepName = (typeof STEPS)[number];

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" aria-hidden="true" className="text-accent">
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
    </svg>
  );
}

export function Stepper({ current }: { current: StepName }) {
  const active = STEPS.indexOf(current);
  return (
    <nav aria-label="Progress">
      <ol className="flex flex-wrap items-center gap-1.5 text-[13px] sm:gap-2">
        {STEPS.map((step, index) => {
          const isActive = index === active;
          const isDone = index < active;
          return (
            <li key={step} className="flex items-center gap-1.5 sm:gap-2">
              {index > 0 && <span aria-hidden="true" className="text-line-strong">—</span>}
              <span
                aria-current={isActive ? "step" : undefined}
                className={`relative rounded-full px-3 py-1.5 ${
                  isActive ? "font-semibold text-white" : isDone ? "text-accent-ink" : "text-muted"
                }`}
              >
                {isActive && (
                  <motion.span
                    layoutId="stepper-pill"
                    className="absolute inset-0 rounded-full bg-accent"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative">{step}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Shell({
  current,
  sessionId,
  onReset,
  children,
}: {
  current: StepName;
  sessionId?: string | null;
  onReset?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3 sm:px-8">
        <button type="button" onClick={onReset} className="flex items-center gap-2.5 rounded-md"
          aria-label="Data Science Agent: start over">
          <Logo />
          <span className="font-display text-[17px] font-semibold">Data Science Agent</span>
        </button>
        <Stepper current={current} />
        <span className="hidden font-mono text-xs text-muted md:block">
          {sessionId ? `session ${sessionId.slice(0, 4)}…${sessionId.slice(-3)}` : " "}
        </span>
      </header>
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}

export function Spinner({ label, className = "text-muted" }: { label: string; className?: string }) {
  return (
    <div role="status" className={`flex items-center gap-3 text-sm ${className}`}>
      <motion.span
        aria-hidden="true"
        className="h-4 w-4 rounded-full border-2 border-accent/25 border-t-accent"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
      />
      {label}
    </div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <motion.p
      role="alert"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"
    >
      {children}
    </motion.p>
  );
}
