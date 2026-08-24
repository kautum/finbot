"use client";

import {
  Bar,
  BarChart,
  Area,
  AreaChart,
  Line,
  LineChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const DATA_COLOURS = [
  "var(--data-1)",
  "var(--data-2)",
  "var(--data-3)",
  "var(--data-4)",
  "var(--data-5)",
];

// Past this many categories, upright labels collide into an unreadable smear no matter
// how far they are rotated. Horizontal bars give each label a full line of its own.
const HORIZONTAL_ABOVE = 12;

export type ChartArgs = {
  kind?: "bar" | "line" | "area";
  title?: string;
  x_key?: string;
  y_keys?: string[];
  data?: Record<string, string | number>[];
};

const axisBase = {
  stroke: "var(--ink-faint)",
  fontSize: 11,
  tickLine: false,
  axisLine: { stroke: "var(--line)" },
};

const tooltipStyle = {
  contentStyle: {
    background: "var(--surface-1)",
    border: "1px solid var(--line)",
    borderRadius: "var(--r-md)",
    fontSize: 12,
    fontVariantNumeric: "tabular-nums" as const,
    color: "var(--ink)",
    boxShadow: "var(--shadow-md)",
  },
  labelStyle: { color: "var(--ink-dim)", marginBottom: 4 },
};

const truncate = (v: unknown, max: number) => {
  const s = String(v ?? "");
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
};

// Recharts' default category tick wraps to fit the axis width, which makes adjacent
// labels overlap once rows are tight. A plain <text> node keeps every label on one line.
function SingleLineTick({ x, y, payload }: any) {
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fill="var(--ink-dim)"
      fontSize={11}
      style={{ pointerEvents: "none" }}
    >
      {truncate(payload?.value, 26)}
    </text>
  );
}

function Frame({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <figure
      style={{
        margin: "14px 0",
        padding: "14px 16px 10px",
        background: "var(--surface-1)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {title && (
        <figcaption
          style={{
            fontSize: 12.5,
            fontWeight: 500,
            color: "var(--ink-dim)",
            marginBottom: 12,
            textWrap: "balance",
          }}
        >
          {title}
        </figcaption>
      )}
      {children}
    </figure>
  );
}

export function ChartCard({ kind = "bar", title, x_key, y_keys, data }: ChartArgs) {
  if (!data?.length || !x_key || !y_keys?.length) return null;

  const multi = y_keys.length > 1;
  const legend = multi ? (
    <Legend wrapperStyle={{ fontSize: 11.5, color: "var(--ink-dim)", paddingTop: 6 }} />
  ) : null;

  if (kind === "bar" && data.length > HORIZONTAL_ABOVE) {
    return (
      <Frame title={title}>
        <ResponsiveContainer width="100%" height={Math.min(data.length * 26 + 44, 900)}>
          <BarChart data={data} layout="vertical" margin={{ top: 2, right: 16, left: 4, bottom: 2 }}>
            <CartesianGrid stroke="var(--line-soft)" horizontal={false} />
            <XAxis type="number" {...axisBase} />
            <YAxis
              type="category"
              dataKey={x_key}
              {...axisBase}
              width={184}
              interval={0}
              tick={<SingleLineTick />}
            />
            <Tooltip cursor={{ fill: "color-mix(in srgb, var(--ink) 5%, transparent)" }} {...tooltipStyle} />
            {legend}
            {y_keys.map((k, i) => (
              <Bar
                key={k}
                dataKey={k}
                fill={DATA_COLOURS[i % DATA_COLOURS.length]}
                radius={[0, 3, 3, 0]}
                maxBarSize={15}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </Frame>
    );
  }

  const Chart = kind === "line" ? LineChart : kind === "area" ? AreaChart : BarChart;
  const rotate = kind === "bar" && data.length > 5;

  return (
    <Frame title={title}>
      <ResponsiveContainer width="100%" height={rotate ? 268 : 218}>
        <Chart data={data} margin={{ top: 4, right: 10, left: -12, bottom: rotate ? 56 : 4 }}>
          <CartesianGrid stroke="var(--line-soft)" vertical={false} />
          <XAxis
            dataKey={x_key}
            {...axisBase}
            tickFormatter={(v) => truncate(v, 16)}
            angle={rotate ? -35 : 0}
            textAnchor={rotate ? "end" : "middle"}
            interval={0}
            height={rotate ? 58 : 24}
          />
          <YAxis {...axisBase} width={54} />
          <Tooltip cursor={{ fill: "color-mix(in srgb, var(--ink) 5%, transparent)" }} {...tooltipStyle} />
          {legend}
          {y_keys.map((k, i) => {
            const c = DATA_COLOURS[i % DATA_COLOURS.length];
            if (kind === "line")
              return <Line key={k} type="monotone" dataKey={k} stroke={c} strokeWidth={1.9} dot={false} />;
            if (kind === "area")
              return (
                <Area key={k} type="monotone" dataKey={k} stroke={c} strokeWidth={1.6} fill={c} fillOpacity={0.16} />
              );
            return <Bar key={k} dataKey={k} fill={c} radius={[3, 3, 0, 0]} maxBarSize={44} />;
          })}
        </Chart>
      </ResponsiveContainer>
    </Frame>
  );
}
