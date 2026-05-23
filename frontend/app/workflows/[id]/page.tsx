"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { Edge, Node } from "reactflow";
import { ArrowLeft, ChevronDown, ChevronRight, Play, Plus, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "@/components/StatusBadge";
import {
  WorkflowCanvas,
  type CanvasNodeData,
  addAgentNode,
  addEndNode,
  addStartNode,
} from "@/components/WorkflowCanvas";
import { NodeInspector } from "@/components/NodeInspector";
import {
  getWorkflow,
  listAgents,
  listRuns,
  runWorkflow,
  updateWorkflow,
} from "@/lib/api";
import type { Agent, Run, Workflow, WorkflowGraph } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";

export default function WorkflowEditorPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const workflowId = Number(params.id);

  const [workflow, setWorkflow] = React.useState<Workflow | null>(null);
  const [agents, setAgents] = React.useState<Agent[]>([]);
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [slackChannel, setSlackChannel] = React.useState("");
  const [graph, setGraph] = React.useState<WorkflowGraph>({
    nodes: [],
    edges: [],
  });

  const [selectedNode, setSelectedNode] =
    React.useState<Node<CanvasNodeData> | null>(null);
  const [selectedEdge, setSelectedEdge] = React.useState<Edge | null>(null);

  const [saving, setSaving] = React.useState(false);
  const [savedAt, setSavedAt] = React.useState<Date | null>(null);

  const [addAgentOpen, setAddAgentOpen] = React.useState(false);
  const [runOpen, setRunOpen] = React.useState(false);
  const [runInput, setRunInput] = React.useState("");
  const [runSubmitting, setRunSubmitting] = React.useState(false);
  const [historyOpen, setHistoryOpen] = React.useState(true);

  React.useEffect(() => {
    if (!Number.isFinite(workflowId)) return;
    let alive = true;
    (async () => {
      try {
        const [w, a, r] = await Promise.all([
          getWorkflow(workflowId),
          listAgents(),
          listRuns({ workflow_id: workflowId, limit: 20 }),
        ]);
        if (!alive) return;
        setWorkflow(w);
        setName(w.name);
        setDescription(w.description);
        setSlackChannel(w.slack_channel ?? "");
        setGraph(w.graph);
        setAgents(a);
        setRuns(r);
      } catch (err) {
        if (!alive) return;
        setError(
          err instanceof Error ? err.message : "Failed to load workflow.",
        );
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [workflowId]);

  const handleCanvasChange = React.useCallback((next: WorkflowGraph) => {
    setGraph(next);
  }, []);

  const handleSave = async () => {
    if (!workflow) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateWorkflow(workflow.id, {
        name: name.trim() || "Untitled Workflow",
        description,
        graph,
        slack_channel: slackChannel.trim() ? slackChannel.trim() : null,
      });
      setWorkflow(updated);
      setSavedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!workflow) return;
    setRunSubmitting(true);
    try {
      const run = await runWorkflow(workflow.id, runInput);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run.");
      setRunSubmitting(false);
    }
  };

  const handleAddAgent = (agent: Agent) => {
    addAgentNode(agent);
    setAddAgentOpen(false);
  };

  const hasStart = graph.nodes.some((n) => n.type === "start");
  const hasEnd = graph.nodes.some((n) => n.type === "end");

  if (loading) {
    return (
      <div className="p-8 text-sm text-muted-foreground">
        Loading workflow…
      </div>
    );
  }

  if (error && !workflow) {
    return (
      <div className="p-8">
        <Link href="/workflows" className="text-sm text-muted-foreground hover:underline inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to workflows
        </Link>
        <p className="mt-4 text-sm text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="border-b border-border bg-card px-6 py-3">
        <div className="flex items-center gap-3 mb-2">
          <Link
            href="/workflows"
            className="text-xs text-muted-foreground hover:underline inline-flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Workflows
          </Link>
          <span className="text-xs text-muted-foreground">/</span>
          <span className="text-xs text-muted-foreground font-mono">
            #{workflow?.id}
          </span>
          {savedAt && (
            <span className="text-xs text-muted-foreground ml-auto">
              Saved {savedAt.toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Workflow name"
            className="text-base font-semibold max-w-xs"
          />
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short description"
            className="max-w-md"
          />
          <Input
            value={slackChannel}
            onChange={(e) => setSlackChannel(e.target.value)}
            placeholder="#agent-demo or Cxxxx"
            className="max-w-[200px]"
          />
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleSave}
              disabled={saving}
            >
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button onClick={() => setRunOpen(true)}>
              <Play className="h-4 w-4" />
              Run
            </Button>
          </div>
        </div>
        {error && (
          <p className="text-xs text-red-600 mt-2">{error}</p>
        )}
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Left palette */}
        <aside className="w-56 shrink-0 border-r border-border bg-card p-4 space-y-3 overflow-y-auto">
          <div>
            <h3 className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
              Palette
            </h3>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => setAddAgentOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
                Add agent node
              </Button>
              {!hasStart && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => addStartNode()}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add start
                </Button>
              )}
              {!hasEnd && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => addEndNode()}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add end
                </Button>
              )}
            </div>
          </div>

          <div className="pt-2 border-t border-border">
            <h3 className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
              Tips
            </h3>
            <ul className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
              <li>Drag from a node handle to connect.</li>
              <li>Select an edge to set a <span className="font-mono">when</span> condition.</li>
              <li>Delete with the inspector.</li>
            </ul>
          </div>
        </aside>

        {/* Center: canvas */}
        <div className="flex-1 min-w-0 relative">
          <WorkflowCanvas
            initialGraph={graph}
            agents={agents}
            onChange={handleCanvasChange}
            onSelectionChange={({ node, edge }) => {
              setSelectedNode(node);
              setSelectedEdge(edge);
            }}
          />
        </div>

        {/* Right inspector */}
        <aside className="w-80 shrink-0 border-l border-border bg-background p-4 overflow-y-auto">
          <NodeInspector
            node={selectedNode}
            edge={selectedEdge}
            agents={agents}
          />
        </aside>
      </div>

      {/* Recent runs strip */}
      <div className="border-t border-border bg-card">
        <button
          type="button"
          onClick={() => setHistoryOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-6 py-2 text-xs uppercase tracking-wide text-muted-foreground hover:bg-muted/50"
        >
          {historyOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Recent runs · {runs.length}
        </button>
        {historyOpen && (
          <div className="max-h-48 overflow-y-auto border-t border-border">
            {runs.length === 0 ? (
              <p className="text-xs text-muted-foreground p-4">
                No runs for this workflow yet.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="text-left font-medium px-6 py-2">Run</th>
                    <th className="text-left font-medium px-4 py-2">Status</th>
                    <th className="text-left font-medium px-4 py-2">Trigger</th>
                    <th className="text-left font-medium px-4 py-2">Started</th>
                    <th className="text-left font-medium px-4 py-2">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-border last:border-0 hover:bg-muted/50"
                    >
                      <td className="px-6 py-2">
                        <Link
                          href={`/runs/${r.id}`}
                          className="font-mono text-xs hover:underline"
                        >
                          #{r.id}
                        </Link>
                      </td>
                      <td className="px-4 py-2">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {r.trigger}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {formatDate(r.started_at)}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {formatDuration(r.started_at, r.finished_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Add Agent dialog */}
      <Dialog open={addAgentOpen} onOpenChange={setAddAgentOpen}>
        <DialogContent className="max-w-lg" onClose={() => setAddAgentOpen(false)}>
          <DialogHeader>
            <DialogTitle>Add agent node</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {agents.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No agents yet.{" "}
                <Link href="/agents" className="underline">
                  Create one
                </Link>{" "}
                first.
              </p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {agents.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => handleAddAgent(a)}
                    className="w-full text-left p-3 rounded-md border border-border hover:bg-muted transition-colors"
                  >
                    <div className="font-medium text-sm">{a.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {a.role}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </DialogBody>
        </DialogContent>
      </Dialog>

      {/* Run dialog */}
      <Dialog open={runOpen} onOpenChange={setRunOpen}>
        <DialogContent className="max-w-lg" onClose={() => setRunOpen(false)}>
          <DialogHeader>
            <DialogTitle>Run workflow</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <Label htmlFor="run-input">Input</Label>
            <Textarea
              id="run-input"
              rows={5}
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              placeholder="What should the workflow process?"
            />
          </DialogBody>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRunOpen(false)}
              disabled={runSubmitting}
            >
              Cancel
            </Button>
            <Button onClick={handleRun} disabled={runSubmitting}>
              <Play className="h-4 w-4" />
              {runSubmitting ? "Starting…" : "Run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

