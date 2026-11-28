// Spec 11 FR-DP-17: liveness for platform health checks. Outside the access gate, so it
// returns nothing but its own status.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return Response.json({ status: "ok" });
}
