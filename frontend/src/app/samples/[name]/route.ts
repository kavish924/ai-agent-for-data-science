import { readFile } from "node:fs/promises";
import path from "node:path";

// Serves the repo's sample datasets for the upload screen's one-click samples
// (Spec 04 FR-RV-13). Only these exact names are served: no path from the URL ever
// reaches the filesystem.
const SAMPLES = new Set(["titanic.csv", "housing.csv", "telco_churn.csv"]);
const SAMPLES_DIR = path.join(process.cwd(), "..", "samples");

export async function GET(_request: Request, context: { params: Promise<{ name: string }> }) {
  const { name } = await context.params;
  if (!SAMPLES.has(name)) return new Response("Not found", { status: 404 });
  try {
    const data = await readFile(path.join(SAMPLES_DIR, name));
    return new Response(new Uint8Array(data), {
      headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "public, max-age=3600" },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
