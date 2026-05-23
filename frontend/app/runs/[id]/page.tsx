"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { RunLogPanel, useRunStream } from "@/components/RunLogStream";
import { getRun, getWorkflow, listAgents } from "@/lib/api";
import type {
  Agent,
  LogEvent,
  Message,
  Run,
  RunStatus,
  Workflow,
} from "@/lib/types";
import {
  formatCost,
  formatDate,
  formatDuration,
  formatTokens,
} from "@/lib/utils";

const TERMINAL: RunStatus[] = ["succeeded", "failed", "cancelled"];

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);

  const [run, setRun] = React.useState<Run | null>(null);
  const [workflow, setWorkflow] = React.useState<Workflow | null>(null);
  const [agents, setAgents] = React.useState<Agent[]>([]);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [logs, setLogs] = React.useState<LogEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!Number.isFinite(runId)) return;
    let alive = true;
    (async () => {
      try {
        const detail = await getRun(runId);
        if (!alive) return;
        setRun(detail.run);
        setMessages(detail.messages);
        setLogs(detail.logs);
        try {
          const [a, w] = await Promise.all([
            listAgents(),
            getWorkflow(detail.run.workflow_id),
          ]);
          if (!alive) return;
          setAgents(a);
          setWorkflow(w);
        } catch {
          // Non-fatal: header just shows less context.
        }
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load run.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [runId]);

  const streaming =
    !!run && !TERMINAL.includes(run.status) && Number.isFinite(runId);

  useRunStream({
    runId,
    enabled: streaming,
    onLog: (log) =>
      setLogs((prev) =>
        prev.some((l) => l.id === log.id) ? prev : [...prev, log],
      ),
    onMessage: (msg) =>
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
      ),
    onStatus: (status) =>
      setRun((prev) => (prev ? { ...prev, status } : prev)),
    onDone: () => {
      // Refresh totals/finished_at when the run completes.
      getRun(runId)
        .then((d) => {
          setRun(d.run);
          setMessages(d.messages);
          setLogs(d.logs);
        })
        .catch(() => {});
    },
  });

  if (loading) {
    return (
      <div className="p-8 text-sm text-muted-foreground">Loading run…</div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-8">
        <Link
          href="/runs"
          className="text-sm text-muted-foreground hover:underline inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to runs
        </Link>
        <p className="mt-4 text-sm text-red-600">{error || "Run not found."}</p>
      </div>
    );
  }

  const agentsById = new Map(agents.map((a) => [a.id, a]));

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <Link
        href="/runs"
        className="text-xs text-muted-foreground hover:underline inline-flex items-center gap-1"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Runs
      </Link>

      <header className="mt-3 mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              {workflow ? workflow.name : `Workflow #${run.workflow_id}`}
            </h1>
            <StatusBadge status={run.status} />
          </div>
          <p className="text-sm text-muted-foreground mt-1 font-mono">
            Run #{run.id} · trigger: {run.trigger}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
          <span className="text-muted-foreground">Started</span>
          <span>{formatDate(run.started_at)}</span>
          <span className="text-muted-foreground">Finished</span>
          <span>{formatDate(run.finished_at)}</span>
          <span className="text-muted-foreground">Duration</span>
          <span>{formatDuration(run.started_at, run.finished_at)}</span>
          <span className="text-muted-foreground">Tokens</span>
          <span>
            {formatTokens(run.total_input_tokens)} in ·{" "}
            {formatTokens(run.total_output_tokens)} out
          </span>
          <span className="text-muted-foreground">Cost</span>
          <span>{formatCost(run.total_cost_usd)}</span>
        </div>
      </header>

      {run.error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2 whitespace-pre-wrap">
          {run.error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Messages</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 max-h-[60vh] overflow-y-auto">
            {messages.length === 0 && (
              <p className="text-sm text-muted-foreground">No messages yet.</p>
            )}
            {messages.map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                agentsById={agentsById}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Live logs</CardTitle>
          </CardHeader>
          <CardContent>
            <RunLogPanel logs={logs} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  agentsById,
}: {
  message: Message;
  agentsById: Map<number, Agent>;
}) {
  const from =
    message.from_agent_id !== null
      ? agentsById.get(message.from_agent_id)?.name ||
        `Agent #${message.from_agent_id}`
      : message.role === "user"
        ? "user"
        : message.role;
  const to =
    message.to_agent_id !== null
      ? agentsById.get(message.to_agent_id)?.name ||
        `Agent #${message.to_agent_id}`
      : "—";

  const isJsonish = (() => {
    const trimmed = message.content.trim();
    return (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    );
  })();

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
        <Badge variant={roleBadge(message.role)}>{message.role}</Badge>
        <span className="font-mono">{from}</span>
        <span>→</span>
        <span className="font-mono">{to}</span>
        <span className="ml-auto">{formatDate(message.created_at)}</span>
      </div>
      {isJsonish ? (
        <pre className="text-xs bg-muted rounded-md p-3 overflow-x-auto whitespace-pre-wrap font-mono">
          {message.content}
        </pre>
      ) : (
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>
      )}
      {(message.tokens_in > 0 || message.tokens_out > 0) && (
        <div className="text-xs text-muted-foreground mt-2">
          {formatTokens(message.tokens_in)} in ·{" "}
          {formatTokens(message.tokens_out)} out
        </div>
      )}
    </div>
  );
}

function roleBadge(
  role: Message["role"],
): "secondary" | "info" | "outline" | "success" {
  switch (role) {
    case "user":
      return "info";
    case "agent":
      return "success";
    case "tool":
      return "outline";
    default:
      return "secondary";
  }
}
