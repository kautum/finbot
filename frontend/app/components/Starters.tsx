"use client";

import { useState } from "react";
import type { Overview } from "../lib/overview";

/* Sample questions, grouped by the kind of analysis. Databricks Genie calls these
   "sample questions" and ThoughtSpot "quickstart suggestions"; both exist because a
   user who does not know what the data holds cannot invent a good first question.
   Grouped by analysis type rather than by table -- the user is picking a question,
   not planning a join. */

export function Starters({
  groups,
  onPick,
  disabled,
}: {
  groups: Overview["question_groups"];
  onPick: (q: string) => void;
  disabled?: boolean;
}) {
  const [active, setActive] = useState(0);
  const group = groups[active];
  if (!group) return null;

  return (
    <div style={{ display: "grid", gap: 14, width: "100%" }}>
      <div role="tablist" aria-label="Question categories" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {groups.map((g, i) => {
          const on = i === active;
          return (
            <button
              key={g.group}
              role="tab"
              aria-selected={on}
              onClick={() => setActive(i)}
              className="pressable"
              style={{
                all: "unset",
                cursor: "pointer",
                padding: "5px 12px",
                borderRadius: 999,
                fontSize: 12.5,
                fontWeight: 500,
                border: "1px solid",
                borderColor: on ? "var(--brand)" : "var(--line)",
                background: on ? "var(--brand)" : "var(--surface-1)",
                color: on ? "var(--on-brand)" : "var(--ink-dim)",
              }}
            >
              {g.group}
            </button>
          );
        })}
      </div>

      <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-faint)" }}>{group.blurb}</p>

      <div
        style={{
          display: "grid",
          gap: 8,
          gridTemplateColumns: "repeat(auto-fit, minmax(228px, 1fr))",
        }}
      >
        {group.questions.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            disabled={disabled}
            className="pressable"
            style={{
              all: "unset",
              boxSizing: "border-box",
              cursor: disabled ? "default" : "pointer",
              opacity: disabled ? 0.55 : 1,
              padding: "12px 14px",
              minHeight: 62,
              display: "flex",
              alignItems: "center",
              background: "var(--surface-1)",
              border: "1px solid var(--line)",
              borderRadius: "var(--r-md)",
              boxShadow: "var(--shadow-sm)",
              fontSize: 13,
              lineHeight: 1.45,
              color: "var(--ink)",
              textWrap: "balance",
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
