"use client";

import { useCallback, useState } from "react";
import { z } from "zod";
import {
  CopilotChat,
  useAgent,
  UseAgentUpdate,
  useConfigureSuggestions,
  useRenderTool,
} from "@copilotkit/react-core/v2";
import { ChartCard } from "./components/ChartCard";
import { SqlCard } from "./components/SqlCard";
import { DataPanel } from "./components/DataPanel";
import { Starters } from "./components/Starters";
import { ThemeToggle } from "./components/ThemeToggle";
import { fmt, useOverview } from "./lib/overview";

const AGENT_ID = "finbot_agent";

// These mirror the Python tool signatures in agent/agent.py. `name` must match exactly.
const sqlParams = z.object({ query: z.string() });

const chartParams = z.object({
  kind: z.enum(["bar", "line", "area"]),
  title: z.string(),
  x_key: z.string(),
  y_keys: z.array(z.string()),
  data: z.array(z.record(z.string(), z.union([z.string(), z.number()]))),
});

export default function Home() {
  const { data: overview } = useOverview();
  // Subscribing to message changes rather than tracking a local flag, so the onboarding
  // hero also clears when the user types their own first question instead of clicking one.
  const { agent, isReady } = useAgent({
    agentId: AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });
  const started = (agent?.messages?.length ?? 0) > 0;
  const [panelOpen, setPanelOpen] = useState(true);

  // Follow ups: grounded in what was just answered, not generic next steps.
  // Only after the first message -- before that, the Starters grid does this job better
  // because it can be grouped and does not cost a model call.
  useConfigureSuggestions({
    instructions:
      "Suggest short follow-up questions that dig into the answer just given -- a narrower " +
      "slice, a time trend, or a comparison against another segment. Ground each one in the " +
      "specific numbers or categories that were just discussed. Never suggest something the " +
      "data cannot answer. Keep each under 9 words.",
    maxSuggestions: 3,
    available: "after-first-message",
    providerAgentId: AGENT_ID,
  });

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

  const ask = useCallback(
    (question: string) => {
      if (!isReady) return;
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: question });
      void agent.runAgent();
    },
    [agent, isReady],
  );

  const s = overview?.stats;

  return (
    <div
      style={{
        height: "100dvh",
        display: "grid",
        gridTemplateRows: "auto 1fr",
        background: "var(--bg)",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "12px 20px",
          borderBottom: "1px solid var(--line)",
          background: "var(--surface-1)",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0 }}>
          <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.015em" }}>Finbot</span>
          <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>AI financial analyst</span>
        </div>

        {s && (
          <span
            className="tnum"
            style={{
              marginLeft: "auto",
              fontSize: 11.5,
              color: "var(--ink-dim)",
              whiteSpace: "nowrap",
            }}
          >
            {fmt(s.labeled_transactions)} transactions · {fmt(s.fraud_cases)} fraud cases
          </span>
        )}

        <button
          onClick={() => setPanelOpen((o) => !o)}
          aria-expanded={panelOpen}
          className="pressable"
          style={{
            all: "unset",
            cursor: "pointer",
            marginLeft: s ? 0 : "auto",
            padding: "5px 11px",
            borderRadius: "var(--r-sm)",
            border: "1px solid var(--line)",
            background: panelOpen ? "var(--brand-wash)" : "var(--surface-1)",
            color: panelOpen ? "var(--brand)" : "var(--ink-dim)",
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          Data
        </button>
        <ThemeToggle />
      </header>

      <div
        style={{
          minHeight: 0,
          display: "grid",
          gridTemplateColumns: panelOpen && overview ? "minmax(0, 1fr) 312px" : "minmax(0, 1fr)",
        }}
      >
        <main style={{ minHeight: 0, display: "grid", gridTemplateRows: "1fr", overflow: "hidden" }}>
          <div
            className={started ? undefined : "finbot-onboarding"}
            style={{
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              maxWidth: 840,
              width: "100%",
              margin: "0 auto",
            }}
          >
            {!started && overview && (
              <div style={{ padding: "34px 24px 6px", display: "grid", gap: 18 }}>
                <div style={{ display: "grid", gap: 6 }}>
                  <h1
                    style={{
                      margin: 0,
                      fontSize: 24,
                      fontWeight: 600,
                      letterSpacing: "-0.025em",
                      textWrap: "balance",
                    }}
                  >
                    Ask anything about {fmt(overview.stats.labeled_transactions)} card
                    transactions.
                  </h1>
                  <p style={{ margin: 0, fontSize: 13.5, color: "var(--ink-dim)", lineHeight: 1.55 }}>
                    Finbot writes the query, runs it, charts the result, and shows its working.
                    Pick a question to start, or ask your own.
                  </p>
                </div>
                <Starters
                  groups={overview.question_groups}
                  onPick={ask}
                  disabled={!isReady}
                />
              </div>
            )}

            <div style={{ minHeight: 0, flex: 1, display: "flex", flexDirection: "column" }}>
              <CopilotChat
                agentId={AGENT_ID}
                labels={{
                  chatInputPlaceholder: "Ask about fraud, spending, merchants, cardholders…",
                }}
              />
            </div>
          </div>
        </main>

        {panelOpen && overview && (
          <aside
            style={{
              borderLeft: "1px solid var(--line)",
              background: "var(--surface-2)",
              padding: 16,
              overflowY: "auto",
              minHeight: 0,
            }}
          >
            <DataPanel data={overview} />
          </aside>
        )}
      </div>
    </div>
  );
}
