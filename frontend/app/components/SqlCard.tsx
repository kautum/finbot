"use client";

import { useState } from "react";

type Status = "inProgress" | "executing" | "complete" | string;

export function SqlCard({
  query,
  status,
  result,
}: {
  query?: string;
  status: Status;
  result?: unknown;
}) {
  const [open, setOpen] = useState(false);
  const running = status !== "complete";

  // The tool returns JSON on success and a string starting with ERROR on failure.
  const raw = typeof result === "string" ? result : result ? JSON.stringify(result) : "";
  const failed = raw.startsWith("ERROR:");
  let rowCount: number | null = null;
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed?.row_count === "number") rowCount = parsed.row_count;
  } catch {
    /* not JSON: an error string or the empty-result message */
  }

  const label = running
    ? "Querying…"
    : failed
      ? "Query failed"
      : rowCount !== null
        ? `${rowCount.toLocaleString()} ${rowCount === 1 ? "row" : "rows"}`
        : "Query complete";

  return (
    <div
      style={{
        margin: "10px 0",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-md)",
        background: "var(--surface-1)",
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          all: "unset",
          display: "flex",
          alignItems: "center",
          gap: 9,
          width: "100%",
          boxSizing: "border-box",
          padding: "8px 12px",
          cursor: "pointer",
          fontSize: 12,
          color: "var(--ink-dim)",
          fontFamily: "var(--font-mono)",
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            flexShrink: 0,
            background: running
              ? "var(--data-3)"
              : failed
                ? "var(--data-4)"
                : "var(--data-2)",
          }}
        />
        <span style={{ letterSpacing: "0.03em" }}>SQL</span>
        <span className="tnum" style={{ color: "var(--ink-faint)" }}>
          {label}
        </span>
        <span style={{ marginLeft: "auto", color: "var(--ink-faint)", fontSize: 11 }}>
          {open ? "hide" : "show"}
        </span>
      </button>

      {open && query && (
        <pre
          style={{
            margin: 0,
            padding: "10px 12px 12px",
            borderTop: "1px solid var(--line-soft)",
            background: "var(--surface-2)",
            color: "var(--ink-dim)",
            fontFamily: "var(--font-mono)",
            fontSize: 11.5,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            overflowX: "auto",
          }}
        >
          {query}
          {failed && (
            <div style={{ color: "var(--data-4)", marginTop: 8 }}>{raw}</div>
          )}
        </pre>
      )}
    </div>
  );
}
