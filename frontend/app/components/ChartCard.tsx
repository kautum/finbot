"use client";

import {
  Bar,
  BarChart,
  Area,
  AreaChart,
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const DATA_COLOURS = ["var(--data-1)", "var(--data-2)", "var(--data-3)", "var(--data-4)"];

export type ChartArgs = {
  kind?: "bar" | "line" | "area";
  title?: string;
  x_key?: string;
  y_keys?: string[];
  data?: Record<string, string | number>[];
};

const axis = {
  stroke: "var(--ink-faint)",
  fontSize: 11,
  tickLine: false,
  axisLine: { stroke: "var(--line)" },
};

function shorten(v: unknown) {
  const s = String(v ?? "");
  return s.length > 18 ? s.slice(0, 17) + "…" : s;
}

export function ChartCard({ kind = "bar", title, x_key, y_keys, data }: ChartArgs) {
  if (!data?.length || !x_key || !y_keys?.length) return null;

  const Chart = kind === "line" ? LineChart : kind === "area" ? AreaChart : BarChart;
  // Long category names need horizontal room; a time series does not.
  const rotate = kind === "bar" && data.length > 5;

  return (
    <figure
      style={{
        margin: "14px 0",
        padding: "16px 16px 8px",
        background: "var(--surface-1)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)",
      }}
    >
      {title && (
        <figcaption
          style={{
            fontSize: 12,
            letterSpacing: "0.02em",
            color: "var(--ink-dim)",
            marginBottom: 14,
            textWrap: "balance",
          }}
        >
          {title}
        </figcaption>
      )}
      <ResponsiveContainer width="100%" height={rotate ? 260 : 210}>
        <Chart data={data} margin={{ top: 4, right: 8, left: -14, bottom: rotate ? 58 : 4 }}>
          <CartesianGrid stroke="var(--line-soft)" vertical={false} />
          <XAxis
            dataKey={x_key}
            {...axis}
            tickFormatter={shorten}
            angle={rotate ? -38 : 0}
            textAnchor={rotate ? "end" : "middle"}
            interval={0}
            height={rotate ? 60 : 24}
          />
          <YAxis {...axis} width={54} />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.035)" }}
            contentStyle={{
              background: "var(--surface-3)",
              border: "1px solid var(--line)",
              borderRadius: "var(--r-md)",
              fontSize: 12,
              fontVariantNumeric: "tabular-nums",
              color: "var(--ink)",
            }}
            labelStyle={{ color: "var(--ink-dim)", marginBottom: 4 }}
          />
          {y_keys.map((k, i) => {
            const c = DATA_COLOURS[i % DATA_COLOURS.length];
            if (kind === "line")
              return <Line key={k} type="monotone" dataKey={k} stroke={c} strokeWidth={1.75} dot={false} />;
            if (kind === "area")
              return (
                <Area key={k} type="monotone" dataKey={k} stroke={c} strokeWidth={1.5} fill={c} fillOpacity={0.14} />
              );
            return <Bar key={k} dataKey={k} fill={c} radius={[3, 3, 0, 0]} maxBarSize={46} />;
          })}
        </Chart>
      </ResponsiveContainer>
    </figure>
  );
}
