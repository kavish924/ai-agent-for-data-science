import { Suspense } from "react";
import { AgentFlow } from "@/components/AgentFlow";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <AgentFlow />
    </Suspense>
  );
}
