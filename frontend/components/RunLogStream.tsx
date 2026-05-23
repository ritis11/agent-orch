"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { LogEvent, Message, RunStatus } from "@/lib/types";

type RunLogStreamProps = {
  runId: number;
  enabled?: boolean;
  onLog?: (log: LogEvent) => void;
  onMessage?: (msg: Message) => void;
  onStatus?: (status: RunStatus) => void;
  onDone?: () => void;
};

export function useRunStream({
  runId,
  enabled = true,
  onLog,
  onMessage,
  onStatus,
  onDone,
}: RunLogStreamProps) {
  // Keep callbacks in refs so we don't need to tear down the EventSource
  // every time the parent re-renders with a new closure.
  const onLogRef = React.useRef(onLog);
  const onMessageRef = React.useRef(onMessage);
  const onStatusRef = React.useRef(onStatus);
  const onDoneRef = React.useRef(onDone);

  React.useEffect(() => {
    onLogRef.current = onLog;
    onMessageRef.current = onMessage;
    onStatusRef.current = onStatus;
    onDoneRef.current = onDone;
  }, [onLog, onMessage, onStatus, onDone]);

  React.useEffect(() => {
    if (!enabled) return;

    const url = api.streamUrl(runId);
    const es = new EventSource(url);

    const handleLog = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as LogEvent;
        onLogRef.current?.(data);
      } catch {
        // ignore malformed payloads
      }
    };
    const handleMessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as Message;
        onMessageRef.current?.(data);
      } catch {
        // ignore malformed payloads
      }
    };
    const handleStatus = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as { status: RunStatus } | RunStatus;
        const status =
          typeof data === "string" ? data : (data?.status as RunStatus);
        if (status) onStatusRef.current?.(status);
      } catch {
        // ignore
      }
    };
    const handleDone = () => {
      onDoneRef.current?.();
      es.close();
    };

    es.addEventListener("log", handleLog);
    es.addEventListener("message", handleMessage);
    es.addEventListener("status", handleStatus);
    es.addEventListener("done", handleDone);

    es.onerror = () => {
      // Browsers will auto-retry. If the run is finished the server will close.
    };

    return () => {
      es.removeEventListener("log", handleLog);
      es.removeEventListener("message", handleMessage);
      es.removeEventListener("status", handleStatus);
      es.removeEventListener("done", handleDone);
      es.close();
    };
  }, [runId, enabled]);
}

type LogPanelProps = {
  logs: LogEvent[];
};

export function RunLogPanel({ logs }: LogPanelProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <div
      ref={scrollRef}
      className="font-mono text-xs bg-card border border-border rounded-lg h-[60vh] overflow-y-auto p-3 space-y-1.5"
    >
      {logs.length === 0 && (
        <div className="text-muted-foreground">No logs yet.</div>
      )}
      {logs.map((log) => (
        <div key={log.id} className="flex items-start gap-2">
          <span
            className={
              log.level === "error"
                ? "h-2 w-2 mt-1.5 rounded-full bg-red-500 shrink-0"
                : log.level === "warn"
                  ? "h-2 w-2 mt-1.5 rounded-full bg-amber-500 shrink-0"
                  : "h-2 w-2 mt-1.5 rounded-full bg-emerald-500 shrink-0"
            }
          />
          <span className="text-muted-foreground shrink-0">
            {new Date(log.created_at).toLocaleTimeString()}
          </span>
          <span className="text-muted-foreground shrink-0">[{log.source}]</span>
          <span className="break-words whitespace-pre-wrap">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
