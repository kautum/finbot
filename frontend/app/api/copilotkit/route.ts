import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

const runtime = new CopilotRuntime({
  agents: {
    finbot_agent: new LangGraphHttpAgent({
      url: process.env.AGENT_URL || "http://localhost:8123",
    }),
  },
});

const serviceAdapter = new ExperimentalEmptyAdapter();

// Note: the v2 client also probes GET /api/copilotkit/info, which 404s here because this
// route has no catch-all segment. Agent discovery still succeeds over POST, so it is only
// console noise -- fix with an [[...rest]] route if it ever matters.
export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};