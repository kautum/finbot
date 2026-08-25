"use client";

import { useEffect, useState } from "react";

export type Overview = {
  stats: {
    labeled_transactions: number;
    unlabeled_transactions: number;
    total_transactions: number;
    fraud_cases: number;
    fraud_rate_pct: number;
    cardholders: number;
    cards: number;
    merchants: number;
    categories: number;
    countries: number;
    first_date: string;
    last_date: string;
    channels: { name: string; transactions: number; fraud_rate_pct: number }[];
  };
  field_groups: { group: string; fields: { name: string; description: string }[] }[];
  question_groups: { group: string; blurb: string; questions: string[] }[];
  caveat: string;
  // Set when the figures came from the committed snapshot because no agent was reachable,
  // which also means the chat cannot answer. See app/api/overview/route.ts.
  snapshot?: boolean;
};

export function useOverview() {
  const [data, setData] = useState<Overview | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    fetch("/api/overview")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => live && setData(d))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  return { data, failed };
}

export const fmt = (n: number) => n.toLocaleString("en-US");

export const year = (iso: string) => iso.slice(0, 4);
