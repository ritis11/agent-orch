"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Workflow as WorkflowIcon, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/EmptyState";
import { createWorkflow, listWorkflows } from "@/lib/api";
import type { Workflow } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const TEMPLATE_NAMES = ["Research & Reply", "Support Triage"];

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = React.useState<Workflow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await listWorkflows();
        if (!alive) return;
        setWorkflows(list);
      } catch (err) {
        if (!alive) return;
        setError(
          err instanceof Error ? err.message : "Failed to load workflows.",
        );
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const templates = workflows.filter((w) => TEMPLATE_NAMES.includes(w.name));
  const others = workflows.filter((w) => !TEMPLATE_NAMES.includes(w.name));

  const handleNew = async () => {
    setCreating(true);
    try {
      const created = await createWorkflow({
        name: "Untitled Workflow",
        description: "",
        graph: {
          nodes: [
            { id: "start", type: "start", position: { x: 80, y: 80 } },
            { id: "end", type: "end", position: { x: 600, y: 80 } },
          ],
          edges: [],
        },
        slack_channel: null,
      });
      router.push(`/workflows/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create workflow.",
      );
      setCreating(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Workflows</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Visual graphs of agents that compile to a real LangGraph runtime.
          </p>
        </div>
        <Button onClick={handleNew} disabled={creating}>
          <Plus className="h-4 w-4" />
          {creating ? "Creating…" : "New workflow"}
        </Button>
      </header>

      {error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {templates.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs uppercase tracking-wide text-muted-foreground mb-3 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5" />
            Templates
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((t) => (
              <Card key={t.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle>{t.name}</CardTitle>
                  <CardDescription>{t.description || "—"}</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center justify-between">
                  <div className="text-xs text-muted-foreground">
                    {t.graph.nodes.length} nodes · {t.graph.edges.length} edges
                  </div>
                  <Link href={`/workflows/${t.id}`}>
                    <Button variant="outline" size="sm">
                      Open
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
          Your workflows
        </h2>

        {loading ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Loading workflows…
            </CardContent>
          </Card>
        ) : others.length === 0 ? (
          <EmptyState
            icon={<WorkflowIcon className="h-5 w-5" />}
            title="No workflows yet"
            description="Create one from scratch or open a template above."
            action={
              <Button onClick={handleNew} disabled={creating}>
                <Plus className="h-4 w-4" />
                {creating ? "Creating…" : "New workflow"}
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {others.map((w) => (
              <Link key={w.id} href={`/workflows/${w.id}`}>
                <Card className="hover:shadow-md transition-shadow h-full">
                  <CardHeader>
                    <CardTitle className="truncate">{w.name}</CardTitle>
                    <CardDescription className="line-clamp-2">
                      {w.description || "No description"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-xs text-muted-foreground">
                      {w.graph.nodes.length} nodes · {w.graph.edges.length}{" "}
                      edges
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Updated {formatDate(w.updated_at)}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
