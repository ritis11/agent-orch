"use client";

import * as React from "react";
import type { Edge, Node } from "reactflow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { Agent } from "@/lib/types";
import {
  type CanvasNodeData,
  deleteEdge,
  deleteNode,
  renameNode,
  updateAgentNodeAgent,
  updateEdgeWhen,
} from "./WorkflowCanvas";
import { Trash2 } from "lucide-react";

type NodeInspectorProps = {
  node: Node<CanvasNodeData> | null;
  edge: Edge | null;
  agents: Agent[];
};

export function NodeInspector({ node, edge, agents }: NodeInspectorProps) {
  if (!node && !edge) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Inspector</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Select a node or edge in the canvas to edit its properties.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (node) return <NodeEditor node={node} agents={agents} />;
  if (edge) return <EdgeEditor edge={edge} />;
  return null;
}

function NodeEditor({
  node,
  agents,
}: {
  node: Node<CanvasNodeData>;
  agents: Agent[];
}) {
  const kind = node.data.nodeKind;
  const [label, setLabel] = React.useState<string>(
    node.data.label || node.data.agent?.name || "",
  );
  const [agentId, setAgentId] = React.useState<string>(
    node.data.agent_id !== undefined ? String(node.data.agent_id) : "",
  );

  React.useEffect(() => {
    setLabel(node.data.label || node.data.agent?.name || "");
    setAgentId(
      node.data.agent_id !== undefined ? String(node.data.agent_id) : "",
    );
  }, [node.id, node.data.label, node.data.agent_id, node.data.agent?.name]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {kind === "agent" ? "Agent node" : kind === "start" ? "Start node" : "End node"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="node-id">Node ID</Label>
          <Input id="node-id" value={node.id} readOnly disabled />
        </div>

        {kind === "agent" && (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="node-label">Display label</Label>
              <Input
                id="node-label"
                value={label}
                onChange={(e) => {
                  setLabel(e.target.value);
                  renameNode(node.id, e.target.value);
                }}
                placeholder="Researcher"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="node-agent">Linked agent</Label>
              <Select
                id="node-agent"
                value={agentId}
                onChange={(e) => {
                  const id = e.target.value;
                  setAgentId(id);
                  const agent = agents.find((a) => String(a.id) === id);
                  if (agent) updateAgentNodeAgent(node.id, agent);
                }}
              >
                <option value="">— Select agent —</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.role}
                  </option>
                ))}
              </Select>
            </div>
          </>
        )}

        {kind !== "agent" && (
          <p className="text-xs text-muted-foreground">
            {kind === "start"
              ? "Marks the entry point of the workflow."
              : "Marks the terminal point of the workflow."}
          </p>
        )}

        <div className="pt-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => deleteNode(node.id)}
            type="button"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete node
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function EdgeEditor({ edge }: { edge: Edge }) {
  const [when, setWhen] = React.useState<string>(
    (edge.data?.when as string | undefined) ?? "",
  );

  React.useEffect(() => {
    setWhen((edge.data?.when as string | undefined) ?? "");
  }, [edge.id, edge.data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edge</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5 text-xs text-muted-foreground">
          <span className="font-mono">{edge.source}</span>
          {" → "}
          <span className="font-mono">{edge.target}</span>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edge-when">Condition (when)</Label>
          <Input
            id="edge-when"
            value={when}
            onChange={(e) => {
              setWhen(e.target.value);
              updateEdgeWhen(edge.id, e.target.value);
            }}
            placeholder="label == 'bug'"
          />
          <p className="text-xs text-muted-foreground">
            Optional. Leave blank for an unconditional edge.
          </p>
        </div>
        <div className="pt-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => deleteEdge(edge.id)}
            type="button"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete edge
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
