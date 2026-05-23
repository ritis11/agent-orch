"use client";

import * as React from "react";
import Link from "next/link";
import { Activity } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { listRuns, listWorkflows } from "@/lib/api";
import type { Run, Workflow } from "@/lib/types";
import {
  formatCost,
  formatDate,
  formatDuration,
  formatTokens,
} from "@/lib/utils";

export default function RunsPage() {
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [workflows, setWorkflows] = React.useState<Workflow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [r, w] = await Promise.all([
          listRuns({ limit: 100 }),
          listWorkflows(),
        ]);
        if (!alive) return;
        setRuns(r);
        setWorkflows(w);
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load runs.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const workflowsById = new Map(workflows.map((w) => [w.id, w]));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Every workflow execution, manual or triggered.
          </p>
        </div>
      </header>

      {error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {loading ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Loading runs…
          </CardContent>
        </Card>
      ) : runs.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-5 w-5" />}
          title="No runs yet"
          description="Once you run a workflow, it will appear here."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-2">Run</th>
                  <th className="text-left font-medium px-4 py-2">Workflow</th>
                  <th className="text-left font-medium px-4 py-2">Status</th>
                  <th className="text-left font-medium px-4 py-2">Trigger</th>
                  <th className="text-left font-medium px-4 py-2">Started</th>
                  <th className="text-left font-medium px-4 py-2">Duration</th>
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
                        {r.trigger}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {formatDate(r.started_at)}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {formatDuration(r.started_at, r.finished_at)}
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
