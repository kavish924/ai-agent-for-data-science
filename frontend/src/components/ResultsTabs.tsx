"use client";

import { motion } from "motion/react";
import { useId, useRef } from "react";

export const RESULT_TABS = [
  { id: "overview", label: "Overview" },
  { id: "charts", label: "Charts" },
  { id: "models", label: "Models" },
  { id: "report", label: "Report" },
] as const;
export type ResultTab = (typeof RESULT_TABS)[number]["id"];

const IDS = RESULT_TABS.map((t) => t.id) as readonly string[];

/** The tab named in `?tab=`, or Overview (Spec 04 FR-RV-17). */
export function readTab(params: URLSearchParams): ResultTab {
  const tab = params.get("tab");
  return tab && IDS.includes(tab) ? (tab as ResultTab) : "overview";
}

/**
 * WAI-ARIA tabs: arrow keys / Home / End move selection and focus, only the active
 * tab is in the tab order, and an indicator glides between tabs (Spec 04 AC-11).
 */
export function ResultsTabs({
  selected,
  onSelect,
  badges = {},
  children,
}: {
  selected: ResultTab;
  onSelect: (tab: ResultTab) => void;
  badges?: Partial<Record<ResultTab, string>>;
  children: (tab: ResultTab) => React.ReactNode;
}) {
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const index = RESULT_TABS.findIndex((t) => t.id === selected);

  function move(to: number) {
    const next = (to + RESULT_TABS.length) % RESULT_TABS.length;
    onSelect(RESULT_TABS[next].id);
    refs.current[next]?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const keys: Record<string, number> = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: RESULT_TABS.length - 1,
    };
    if (event.key in keys) {
      event.preventDefault();
      move(keys[event.key]);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div
        role="tablist"
        aria-label="Results"
        onKeyDown={onKeyDown}
        className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line"
      >
        {RESULT_TABS.map((tab, i) => {
          const active = tab.id === selected;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                refs.current[i] = el;
              }}
              id={`${base}-tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={active}
              aria-controls={`${base}-panel-${tab.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => onSelect(tab.id)}
              className={`relative flex h-11 shrink-0 items-center gap-2 rounded-md px-4 text-sm font-medium transition-colors focus-visible:outline-offset-[-3px] ${
                active ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {tab.label}
              {badges[tab.id] && (
                <span aria-hidden="true" className="rounded-full bg-sunken px-1.5 text-[11px] text-ink-soft">
                  {badges[tab.id]}
                </span>
              )}
              {active && (
                <motion.span
                  layoutId={`${base}-indicator`}
                  className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-accent"
                  transition={{ type: "spring", visualDuration: 0.25, bounce: 0.2 }}
                />
              )}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${base}-panel-${selected}`}
        aria-labelledby={`${base}-tab-${selected}`}
        tabIndex={0}
        className="rounded-xl focus-visible:outline-offset-4"
      >
        {children(selected)}
      </div>
    </div>
  );
}
