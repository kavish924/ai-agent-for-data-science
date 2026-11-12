"use client";

import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { api, ApiError, type Session } from "@/lib/api/client";
import { ErrorNote, Spinner } from "./Shell";

const SAMPLES = ["titanic.csv", "housing.csv", "telco_churn.csv"] as const;

const PROMISES = [
  ["Private by design", "The AI sees column statistics only, never your rows."],
  ["You approve every step", "Approve, edit or skip each proposed change."],
  ["Original untouched", "Cleaning writes a new file; your upload never changes."],
] as const;

export function UploadScreen({ onUploaded }: { onUploaded: (session: Session) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(file: File) {
    setBusy(`Uploading ${file.name}…`);
    setError(null);
    try {
      onUploaded(await api.upload(file));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
      setBusy(null);
    }
  }

  async function loadSample(name: string) {
    setBusy(`Loading ${name}…`);
    setError(null);
    try {
      const response = await fetch(`/samples/${name}`);
      if (!response.ok) throw new Error("missing sample");
      const blob = await response.blob();
      await send(new File([blob], name, { type: "text/csv" }));
    } catch {
      setError(`Couldn't load the ${name} sample.`);
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col items-center gap-7 px-4 pb-16 pt-14 sm:pt-20">
      <div className="text-center">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-[40px] sm:leading-tight">
          From raw CSV to a clean dataset you can trust
        </h1>
        <p className="mx-auto mt-3.5 max-w-xl text-base leading-relaxed text-ink-soft">
          The agent profiles your data, proposes a cleaning plan with a reason for every step, and
          changes nothing until you approve it.
        </p>
      </div>

      <motion.label
        htmlFor="csv-file"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files[0];
          if (file) void send(file);
        }}
        animate={{ scale: dragging ? 1.015 : 1 }}
        className={`flex w-full cursor-pointer flex-col items-center gap-3.5 rounded-2xl border-2 border-dashed bg-surface px-6 py-12 text-center transition-colors ${
          dragging ? "border-accent bg-accent-soft" : "border-[#9cc7c1] hover:border-accent"
        }`}
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-accent">
          <path d="M12 16V4M7 9l5-5 5 5" />
          <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        <span className="text-lg font-semibold">Drop a CSV here, or browse</span>
        <span className="text-[13px] text-muted">Up to 25 MB and 100,000 rows · any delimiter or encoding</span>
        <input
          id="csv-file"
          ref={input}
          type="file"
          accept=".csv,text/csv"
          disabled={busy !== null}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void send(file);
            event.target.value = "";
          }}
        />
      </motion.label>

      <div className="flex flex-wrap items-center justify-center gap-2.5 text-[13px] text-muted">
        <span>Or try a sample:</span>
        {SAMPLES.map((name) => (
          <button
            key={name}
            type="button"
            disabled={busy !== null}
            onClick={() => void loadSample(name)}
            className="h-9 rounded-full border border-line-strong bg-surface px-3.5 font-mono text-[13px] font-medium text-ink transition-colors hover:border-accent hover:text-accent-ink disabled:opacity-50"
          >
            {name}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="w-full">
        {busy && <Spinner label={busy} />}
        {error && <ErrorNote>{error}</ErrorNote>}
      </div>

      <ul className="grid w-full grid-cols-1 gap-4 sm:grid-cols-3">
        {PROMISES.map(([title, body], index) => (
          <motion.li
            key={title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 * index + 0.1 }}
            className="rounded-xl border border-line bg-surface p-5"
          >
            <p className="text-sm font-semibold">{title}</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{body}</p>
          </motion.li>
        ))}
      </ul>
    </main>
  );
}
