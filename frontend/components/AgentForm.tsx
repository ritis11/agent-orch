"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import type { Agent, AgentInput, Tool } from "@/lib/types";

type AgentFormProps = {
  initial?: Agent | null;
  models: string[];
  tools: Tool[];
  onSubmit: (data: AgentInput) => Promise<void> | void;
  onCancel: () => void;
  submitting?: boolean;
};

const DEFAULTS: AgentInput = {
  name: "",
  role: "",
  system_prompt: "",
  model: "",
  tools: [],
  memory_window: 10,
  temperature: 0.7,
  max_tokens: 1024,
  guardrails: { blocked_topics: [], max_steps: 8 },
  schedule_cron: null,
  schedule_input: null,
};

export function AgentForm({
  initial,
  models,
  tools,
  onSubmit,
  onCancel,
  submitting,
}: AgentFormProps) {
  const [name, setName] = React.useState(initial?.name ?? DEFAULTS.name);
  const [role, setRole] = React.useState(initial?.role ?? DEFAULTS.role);
  const [systemPrompt, setSystemPrompt] = React.useState(
    initial?.system_prompt ?? DEFAULTS.system_prompt,
  );
  const [model, setModel] = React.useState(
    initial?.model ?? models[0] ?? DEFAULTS.model,
  );
  const [selectedTools, setSelectedTools] = React.useState<string[]>(
    initial?.tools ?? [],
  );
  const [memoryWindow, setMemoryWindow] = React.useState<number>(
    initial?.memory_window ?? DEFAULTS.memory_window,
  );
  const [temperature, setTemperature] = React.useState<number>(
    initial?.temperature ?? DEFAULTS.temperature,
  );
  const [maxTokens, setMaxTokens] = React.useState<number>(
    initial?.max_tokens ?? DEFAULTS.max_tokens,
  );
  const [blockedTopics, setBlockedTopics] = React.useState<string>(
    initial?.guardrails.blocked_topics.join(", ") ?? "",
  );
  const [maxSteps, setMaxSteps] = React.useState<number>(
    initial?.guardrails.max_steps ?? DEFAULTS.guardrails.max_steps,
  );
  const [scheduleCron, setScheduleCron] = React.useState<string>(
    initial?.schedule_cron ?? "",
  );
  const [scheduleInput, setScheduleInput] = React.useState<string>(
    initial?.schedule_input ?? "",
  );
  const [error, setError] = React.useState<string | null>(null);

  // Keep model selection valid once the models list resolves.
  React.useEffect(() => {
    if (!model && models.length > 0) setModel(models[0]);
  }, [models, model]);

  const toggleTool = (toolName: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolName)
        ? prev.filter((t) => t !== toolName)
        : [...prev, toolName],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Name is required.");
    if (!role.trim()) return setError("Role is required.");
    if (!systemPrompt.trim()) return setError("System prompt is required.");
    if (!model.trim()) return setError("Model is required.");

    const data: AgentInput = {
      name: name.trim(),
      role: role.trim(),
      system_prompt: systemPrompt,
      model,
      tools: selectedTools,
      memory_window: Number(memoryWindow),
      temperature: Number(temperature),
      max_tokens: Number(maxTokens),
      guardrails: {
        blocked_topics: blockedTopics
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        max_steps: Number(maxSteps),
      },
      schedule_cron: scheduleCron.trim() ? scheduleCron.trim() : null,
      schedule_input: scheduleInput.trim() ? scheduleInput.trim() : null,
    };

    try {
      await onSubmit(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save agent.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Researcher"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="role">Role</Label>
          <Input
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Gathers facts via web search"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="system_prompt">System Prompt</Label>
        <Textarea
          id="system_prompt"
          rows={5}
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="You are a careful researcher..."
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="model">Model</Label>
          <Select
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {models.length === 0 && <option value="">No models loaded</option>}
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Tools</Label>
          <div className="border border-border rounded-md p-2 max-h-32 overflow-y-auto space-y-1 bg-background">
            {tools.length === 0 && (
              <p className="text-xs text-muted-foreground px-1">
                No tools available.
              </p>
            )}
            {tools.map((tool) => (
              <label
                key={tool.name}
                className="flex items-start gap-2 text-sm cursor-pointer px-1 py-1 rounded hover:bg-muted"
              >
                <input
                  type="checkbox"
                  checked={selectedTools.includes(tool.name)}
                  onChange={() => toggleTool(tool.name)}
                  className="mt-0.5 accent-foreground"
                />
                <span>
                  <span className="font-medium">{tool.name}</span>
                  {tool.description && (
                    <span className="text-muted-foreground">
                      {" "}
                      — {tool.description}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="memory_window">Memory window</Label>
          <Input
            id="memory_window"
            type="number"
            min={0}
            step={1}
            value={memoryWindow}
            onChange={(e) => setMemoryWindow(Number(e.target.value))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="temperature">Temperature</Label>
          <Input
            id="temperature"
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="max_tokens">Max tokens</Label>
          <Input
            id="max_tokens"
            type="number"
            min={1}
            step={1}
            value={maxTokens}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="blocked_topics">Blocked topics (comma-separated)</Label>
          <Input
            id="blocked_topics"
            value={blockedTopics}
            onChange={(e) => setBlockedTopics(e.target.value)}
            placeholder="medical, legal"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="max_steps">Max steps</Label>
          <Input
            id="max_steps"
            type="number"
            min={1}
            step={1}
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="schedule_cron">Schedule cron</Label>
          <Input
            id="schedule_cron"
            value={scheduleCron}
            onChange={(e) => setScheduleCron(e.target.value)}
            placeholder="0 9 * * *"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="schedule_input">Schedule input</Label>
          <Input
            id="schedule_input"
            value={scheduleInput}
            onChange={(e) => setScheduleInput(e.target.value)}
            placeholder="Run daily standup"
          />
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : initial ? "Save changes" : "Create agent"}
        </Button>
      </div>
    </form>
  );
}
