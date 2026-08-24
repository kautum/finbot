"use client";

import { z } from "zod";
import {
  CopilotChat,
  useConfigureSuggestions,
  useRenderTool,
} from "@copilotkit/react-core/v2";
import { ChartCard } from "./components/ChartCard";
import { SqlCard } from "./components/SqlCard";

// These mirror the Python tool signatures in agent/agent.py. The `name` must match exactly.
const sqlParams = z.object({ query: z.string() });

const chartParams = z.object({
  kind: z.enum(["bar", "line", "area"]),
  title: z.string(),
  x_key: z.string(),
  y_keys: z.array(z.string()),
  data: z.array(z.record(z.string(), z.union([z.string(), z.number()]))),
});

const AGENT_ID = "finbot_agent";

const STARTERS = [
  "Which channel has the worst fraud rate?",
  "Show me fraud by merchant category",
  "How has spending changed year over year?",
  "Does credit score predict fraud?",
];

export default function Home() {
  useConfigureSuggestions({
    suggestions: STARTERS.map((title) => ({ title, message: title })),
    available: "before-first-message",
  });

  // Every SQL call the agent makes is shown, not hidden. This is the "shows its work"
  // half of the product -- an answer you cannot audit is not an analyst's answer.
  useRenderTool({
    name: "run_sql",
    agentId: AGENT_ID,
    parameters: sqlParams,
    render: (props) => (
      <SqlCard
        query={props.parameters?.query}
        status={props.status}
        result={"result" in props ? props.result : undefined}
      />
    ),
  });

  useRenderTool({
    name: "chart",
    agentId: AGENT_ID,
    parameters: chartParams,
    render: (props) =>
      props.status === "complete" && props.parameters ? (
        <ChartCard {...props.parameters} />
      ) : (
        <></>
      ),
  });

  return (
    <main
      style={{
        height: "100dvh",
        display: "grid",
        gridTemplateRows: "auto 1fr",
        maxWidth: 820,
        margin: "0 auto",
        width: "100%",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
          padding: "20px 24px 14px",
          borderBottom: "1px solid var(--line-soft)",
        }}
      >
        <h1 style={{ margin: 0, fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>
          Finbot
        </h1>
        <p className="tnum" style={{ margin: 0, fontSize: 12, color: "var(--ink-faint)" }}>
          8,914,963 labeled transactions · 2010–2019
        </p>
      </header>

      <div style={{ minHeight: 0, display: "flex", flexDirection: "column" }}>
        <CopilotChat
          agentId={AGENT_ID}
          labels={{
            chatInputPlaceholder: "Ask about fraud, spending, merchants, cardholders…",
          }}
        />
      </div>
    </main>
  );
}
