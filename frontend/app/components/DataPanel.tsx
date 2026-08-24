"use client";

import { useState } from "react";
import { fmt, year, type Overview } from "../lib/overview";

/* The discovery panel. Every product in this space ships one -- Genie calls it the
   Catalog Explorer, ThoughtSpot a data source picker -- because a chat box with no
   visible data is a blank page you cannot start from. */

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        background: "var(--surface-1)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-md)",
        minWidth: 0,
      }}
    >
      <div
        className="tnum"
        style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.2 }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-dim)", marginTop: 3 }}>{label}</div>
      {hint && (
        <div style={{ fontSize: 10.5, color: "var(--ink-faint)", marginTop: 1 }}>{hint}</div>
      )}
    </div>
  );
}

function ChannelBar({ channels }: { channels: Overview["stats"]["channels"] }) {
  const worst = Math.max(...channels.map((c) => c.fraud_rate_pct));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {channels.map((c) => (
        <div key={c.name} style={{ display: "grid", gap: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: "var(--ink-dim)" }}>{c.name}</span>
            <span className="tnum" style={{ color: "var(--ink)", fontWeight: 500 }}>
              {c.fraud_rate_pct}%
            </span>
          </div>
          <div
            style={{
              height: 5,
              borderRadius: 3,
              background: "var(--surface-3)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                // Square-rooted: the real spread is 353x, and a linear bar renders the
                // two smaller channels as invisible slivers. The number beside it carries
                // the exact value, so the bar only has to convey rank and rough scale.
                width: `${Math.sqrt(c.fraud_rate_pct / worst) * 100}%`,
                height: "100%",
                background: "var(--data-4)",
                borderRadius: 3,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DataPanel({ data }: { data: Overview }) {
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const s = data.stats;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div
        style={{
          display: "grid",
          gap: 8,
          gridTemplateColumns: "repeat(auto-fit, minmax(112px, 1fr))",
        }}
      >
        <Stat label="Transactions" value={fmt(s.labeled_transactions)} hint="fraud-labelled" />
        <Stat
          label="Confirmed fraud"
          value={fmt(s.fraud_cases)}
          hint={`${s.fraud_rate_pct}% of all`}
        />
        <Stat label="Cardholders" value={fmt(s.cardholders)} hint={`${fmt(s.cards)} cards`} />
        <Stat label="Merchants" value={fmt(s.merchants)} hint={`${s.categories} categories`} />
        <Stat
          label="Years covered"
          value={`${year(s.first_date)}–${year(s.last_date)}`}
          hint={`${s.countries} countries`}
        />
      </div>

      <section style={{ display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 12, fontWeight: 600, color: "var(--ink-dim)" }}>
          Fraud rate by channel
        </h2>
        <ChannelBar channels={s.channels} />
      </section>

      <section style={{ display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 12, fontWeight: 600, color: "var(--ink-dim)" }}>
          What you can slice by
        </h2>
        <div style={{ display: "grid", gap: 6 }}>
          {data.field_groups.map((g) => {
            const open = openGroup === g.group;
            return (
              <div
                key={g.group}
                style={{
                  border: "1px solid var(--line)",
                  borderRadius: "var(--r-md)",
                  background: "var(--surface-1)",
                  overflow: "hidden",
                }}
              >
                <button
                  onClick={() => setOpenGroup(open ? null : g.group)}
                  aria-expanded={open}
                  className="pressable"
                  style={{
                    all: "unset",
                    boxSizing: "border-box",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    padding: "8px 11px",
                    cursor: "pointer",
                    fontSize: 12.5,
                    fontWeight: 500,
                  }}
                >
                  <span>{g.group}</span>
                  <span className="tnum" style={{ color: "var(--ink-faint)", fontSize: 11 }}>
                    {g.fields.length}
                  </span>
                  <span
                    aria-hidden="true"
                    style={{
                      marginLeft: "auto",
                      color: "var(--ink-faint)",
                      fontSize: 11,
                      transform: open ? "rotate(90deg)" : "none",
                      transition: "transform 180ms var(--ease)",
                    }}
                  >
                    ›
                  </span>
                </button>
                {open && (
                  <dl
                    style={{
                      margin: 0,
                      padding: "2px 11px 10px",
                      display: "grid",
                      gap: 5,
                      borderTop: "1px solid var(--line-soft)",
                    }}
                  >
                    {g.fields.map((f) => (
                      <div key={f.name} style={{ display: "grid", gap: 1 }}>
                        <dt
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--brand)",
                          }}
                        >
                          {f.name}
                        </dt>
                        <dd style={{ margin: 0, fontSize: 11.5, color: "var(--ink-dim)" }}>
                          {f.description}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <p
        style={{
          margin: 0,
          padding: "9px 11px",
          fontSize: 11.5,
          lineHeight: 1.55,
          color: "var(--ink-dim)",
          background: "var(--brand-wash)",
          border: "1px solid var(--line)",
          borderRadius: "var(--r-md)",
        }}
      >
        {data.caveat}
      </p>
    </div>
  );
}
