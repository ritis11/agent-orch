"use client";

import * as React from "react";
import { Plus, Users, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/EmptyState";
import { AgentForm } from "@/components/AgentForm";
import {
  createAgent,
  deleteAgent,
  listAgents,
  listModels,
  listTools,
  updateAgent,
} from "@/lib/api";
import type { Agent, AgentInput, Tool } from "@/lib/types";

export default function AgentsPage() {
  const [agents, setAgents] = React.useState<Agent[]>([]);
  const [models, setModels] = React.useState<string[]>([]);
  const [tools, setTools] = React.useState<Tool[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Agent | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const refresh = React.useCallback(async () => {
    try {
      const list = await listAgents();
      setAgents(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents.");
    }
  }, []);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [a, m, t] = await Promise.all([
          listAgents(),
          listModels(),
          listTools(),
        ]);
        if (!alive) return;
        setAgents(a);
        setModels(m);
        setTools(t);
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load agents.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const handleNew = () => {
    setEditing(null);
    setOpen(true);
  };

  const handleEdit = (agent: Agent) => {
    setEditing(agent);
    setOpen(true);
  };

  const handleDelete = async (agent: Agent) => {
    if (!confirm(`Delete agent "${agent.name}"?`)) return;
    try {
      await deleteAgent(agent.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent.");
    }
  };

  const handleSubmit = async (data: AgentInput) => {
    setSubmitting(true);
    try {
      if (editing) {
        await updateAgent(editing.id, data);
      } else {
        await createAgent(data);
      }
      setOpen(false);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure agents with tools, memory, guardrails, and schedules.
          </p>
        </div>
        <Button onClick={handleNew}>
          <Plus className="h-4 w-4" />
          New agent
        </Button>
      </header>

      {error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {loading ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Loading agents…
          </CardContent>
        </Card>
      ) : agents.length === 0 ? (
        <EmptyState
          icon={<Users className="h-5 w-5" />}
          title="No agents yet"
          description="Create your first agent to use it in a workflow."
          action={
            <Button onClick={handleNew}>
              <Plus className="h-4 w-4" />
              New agent
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-2">Name</th>
                  <th className="text-left font-medium px-4 py-2">Role</th>
                  <th className="text-left font-medium px-4 py-2">Model</th>
                  <th className="text-left font-medium px-4 py-2">Tools</th>
                  <th className="text-left font-medium px-4 py-2">Schedule</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr
                    key={a.id}
                    className="border-b border-border last:border-0 hover:bg-muted/50 cursor-pointer"
                    onClick={() => handleEdit(a)}
                  >
                    <td className="px-4 py-2.5 font-medium">{a.name}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {a.role}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{a.model}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {a.tools.length === 0 ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          a.tools.map((t) => (
                            <Badge key={t} variant="secondary">
                              {t}
                            </Badge>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {a.schedule_cron || "—"}
                    </td>
                    <td
                      className="px-4 py-2.5 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(a)}
                          aria-label="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(a)}
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent onClose={() => setOpen(false)}>
          <DialogHeader>
            <DialogTitle>
              {editing ? `Edit "${editing.name}"` : "New agent"}
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            <AgentForm
              initial={editing}
              models={models}
              tools={tools}
              onSubmit={handleSubmit}
              onCancel={() => setOpen(false)}
              submitting={submitting}
            />
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  );
}
