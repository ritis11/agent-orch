"use client";

import * as React from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import {
  listAgents,
  listRuns,
  listWorkflows,
} from "@/lib/api";
import type { Agent, Run, Workflow } from "@/lib/types";
import {
  formatCost,
  formatDate,
  formatTokens,
} from "@/lib/utils";
import { Activity } from "lucide-react";

export default function DashboardPage() {
  const [agents, setAgents] = React.useState<Agent[]>([]);
  const [workflows, setWorkflows] = React.useState<Workflow[]>([]);
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [a, w, r] = await Promise.all([
          listAgents(),
          listWorkflows(),
          listRuns({ limit: 10 }),
        ]);
        if (!alive) return;
        setAgents(a);
        setWorkflows(w);
        setRuns(r);
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const runsToday = runs.filter((r) => {
    if (!r.started_at) return false;
    return new Date(r.started_at).getTime() >= today.getTime();
  }).length;
  const totalCost = runs.reduce((acc, r) => acc + (r.total_cost_usd || 0), 0);

  const workflowsById = new Map(workflows.map((w) => [w.id, w]));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Snapshot of agents, workflows and recent runs.
          </p>
        </div>
      </header>

      {error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Agents" value={agents.length} loading={loading} />
        <StatCard
          label="Workflows"
          value={workflows.length}
          loading={loading}
        />
        <StatCard label="Runs today" value={runsToday} loading={loading} />
        <StatCard
          label="Total cost"
          value={formatCost(totalCost)}
          loading={loading}
        />
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle>Recent runs</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {runs.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={<Activity className="h-5 w-5" />}
                  title="No runs yet"
                  description="Trigger a workflow to see runs appear here."
                />
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="text-left font-medium px-4 py-2">Run</th>
                    <th className="text-left font-medium px-4 py-2">Workflow</th>
                    <th className="text-left font-medium px-4 py-2">Status</th>
                    <th className="text-left font-medium px-4 py-2">Started</th>
                    <th className="text-right font-medium px-4 py-2">Tokens</th>
                    <th className="text-right font-medium px-4 py-2">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => {
                    const wf = workflowsById.get(r.workflow_id);
                    return (
                      <tr
                        key={r.id}
                        className="border-b border-border last:border-0 hover:bg-muted/50"
                      >
                        <td className="px-4 py-2.5">
                          <Link
                            href={`/runs/${r.id}`}
                            className="font-mono text-xs hover:underline"
                          >
                            #{r.id}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5">
                          {wf ? (
                            <Link
                              href={`/workflows/${wf.id}`}
                              className="hover:underline"
                            >
                              {wf.name}
                            </Link>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={r.status} />
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">
                          {formatDate(r.started_at)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {formatTokens(
                            (r.total_input_tokens || 0) +
                              (r.total_output_tokens || 0),
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {formatCost(r.total_cost_usd)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  loading,
}: {
  label: string;
  value: number | string;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className="mt-2 text-2xl font-semibold tracking-tight">
          {loading ? "—" : value}
        </div>
      </CardContent>
    </Card>
  );
}
