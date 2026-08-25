"use client";

import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Group = { label: string; events: number; total: number; rate_pct: number; ci_pct: [number, number] };

// The three statistics.py return shapes, discriminated below by which keys are present --
// they are plain dicts on the Python side, not tagged unions.
type TwoRates = {
  groups: [Group, Group];
  conclusion: string;
  p_value_display?: string;
  significant?: boolean;
  risk_ratio?: { value: number; ci: [number, number] | null; note?: string | null };
  effect_size?: { magnitude: string; cohens_h: number; cohens_h_magnitude: string };
};
type Interval = Group & { conclusion: string; confidence_level: number };
type ManyRates = {
  groups: (Group & { p_adjusted_display?: string; differs_from_rest?: boolean })[];
  conclusion: string;
  p_value_display?: string;
  warning?: string;
};

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <figure
      style={{
        margin: "14px 0",
        padding: "14px 16px",
        background: "var(--surface-1)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {children}
    </figure>
  );
}

function RateChart({ groups }: { groups: Group[] }) {
  const data = groups.map((g) => ({
    label: g.label,
    rate_pct: g.rate_pct,
    // Recharts ErrorBar takes [lowMargin, highMargin] for an asymmetric whisker.
    error: [g.rate_pct - g.ci_pct[0], g.ci_pct[1] - g.rate_pct],
  }));
  const rotate = groups.length > 3;
  return (
    <ResponsiveContainer width="100%" height={rotate ? 200 : 140}>
      <BarChart data={data} margin={{ top: 6, right: 10, left: -12, bottom: rotate ? 46 : 4 }}>
        <CartesianGrid stroke="var(--line-soft)" vertical={false} />
        <XAxis
          dataKey="label"
          stroke="var(--ink-faint)"
          fontSize={11}
          tickLine={false}
          axisLine={{ stroke: "var(--line)" }}
          angle={rotate ? -30 : 0}
          textAnchor={rotate ? "end" : "middle"}
          height={rotate ? 52 : 24}
          interval={0}
        />
        <YAxis stroke="var(--ink-faint)" fontSize={11} tickLine={false} axisLine={{ stroke: "var(--line)" }} width={46} />
        <Tooltip
          formatter={(v) => `${Number(v).toFixed(4)}%`}
          contentStyle={{
            background: "var(--surface-1)",
            border: "1px solid var(--line)",
            borderRadius: "var(--r-md)",
            fontSize: 12,
            color: "var(--ink)",
          }}
        />
        <Bar dataKey="rate_pct" fill="var(--data-1)" radius={[3, 3, 0, 0]} maxBarSize={44}>
          <ErrorBar dataKey="error" width={4} strokeWidth={1.5} stroke="var(--ink-dim)" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Verdict({ text, significant }: { text: string; significant?: boolean }) {
  return (
    <p
      style={{
        margin: "0 0 10px",
        fontSize: 13,
        lineHeight: 1.5,
        color: "var(--ink)",
        fontWeight: 500,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          display: "inline-block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          marginRight: 7,
          background: significant === false ? "var(--ink-faint)" : "var(--brand)",
        }}
      />
      {text}
    </p>
  );
}

function Secondary({ children }: { children: React.ReactNode }) {
  return (
    <p className="tnum" style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--ink-faint)" }}>
      {children}
    </p>
  );
}

export function StatCard({ result }: { result?: unknown }) {
  const raw = typeof result === "string" ? result : result ? JSON.stringify(result) : "";
  if (!raw) return null;

  if (raw.startsWith("ERROR:")) {
    return (
      <Frame>
        <Verdict text={raw.slice("ERROR:".length).trim()} significant={false} />
      </Frame>
    );
  }

  let j: any;
  try {
    j = JSON.parse(raw);
  } catch {
    return null;
  }

  // compare_many_rates: has "groups_tested". rate_interval: has "label" but no "groups".
  // compare_two_rates: has "groups" (length 2) and no "groups_tested".
  if ("groups_tested" in j) {
    const d = j as ManyRates;
    return (
      <Frame>
        <Verdict text={d.conclusion} />
        <RateChart groups={d.groups} />
        <Secondary>
          chi-square p {d.p_value_display} across {d.groups.length} groups
          {d.warning ? ` -- ${d.warning}` : ""}
        </Secondary>
      </Frame>
    );
  }

  if (!("groups" in j)) {
    const d = j as Interval;
    return (
      <Frame>
        <Verdict text={d.conclusion} />
        <RateChart groups={[d]} />
        <Secondary>
          {d.rate_pct.toFixed(4)}% ({Math.round(d.confidence_level * 100)}% CI {d.ci_pct[0].toFixed(4)}%
          {"–"}
          {d.ci_pct[1].toFixed(4)}%), {d.events.toLocaleString()} events in {d.total.toLocaleString()}
        </Secondary>
      </Frame>
    );
  }

  const d = j as TwoRates;
  return (
    <Frame>
      <Verdict text={d.conclusion} significant={d.significant} />
      <RateChart groups={d.groups} />
      <Secondary>
        p {d.p_value_display}
        {d.risk_ratio?.value != null && ` · risk ratio ${d.risk_ratio.value}x`}
        {d.effect_size && ` · ${d.effect_size.magnitude} effect (Cohen's h ${d.effect_size.cohens_h}, ${d.effect_size.cohens_h_magnitude} -- see caveat)`}
      </Secondary>
    </Frame>
  );
}
