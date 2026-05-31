"use client";

import * as React from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type OnSelectionChangeParams,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import type { Agent, GraphEdge, GraphNode, WorkflowGraph } from "@/lib/types";
import { cn } from "@/lib/utils";

export type CanvasNodeData = {
  label?: string;
  agent_id?: number;
  agent?: Agent | null;
  nodeKind: "start" | "agent" | "end";
};

type WorkflowCanvasProps = {
  initialGraph: WorkflowGraph;
  agents: Agent[];
  onChange?: (graph: WorkflowGraph) => void;
  onSelectionChange?: (selection: {
    node: Node<CanvasNodeData> | null;
    edge: Edge | null;
  }) => void;
};

const NODE_WIDTH = 200;

// Shared handle styling so the connection dots are visible and easy to grab.
const HANDLE_CLASS = "!h-3 !w-3 !bg-foreground !border-2 !border-card";

function StartNode({ selected }: NodeProps<CanvasNodeData>) {
  return (
    <div
      className={cn(
        "px-4 py-2 rounded-full border bg-card flex items-center gap-2 shadow-sm",
        selected ? "ring-2 ring-foreground" : "border-border",
      )}
    >
      <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
      <span className="text-sm font-medium">Start</span>
      <Handle
        type="source"
        position={Position.Right}
        className={HANDLE_CLASS}
      />
    </div>
  );
}

function EndNode({ selected }: NodeProps<CanvasNodeData>) {
  return (
    <div
      className={cn(
        "px-4 py-2 rounded-full border bg-card flex items-center gap-2 shadow-sm",
        selected ? "ring-2 ring-foreground" : "border-border",
      )}
    >
      <Handle type="target" position={Position.Left} className={HANDLE_CLASS} />
      <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
      <span className="text-sm font-medium">End</span>
    </div>
  );
}

function AgentNode({ data, selected }: NodeProps<CanvasNodeData>) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card shadow-sm min-w-[180px] max-w-[220px]",
        selected ? "ring-2 ring-foreground border-foreground" : "border-border",
      )}
    >
      <Handle type="target" position={Position.Left} className={HANDLE_CLASS} />
      <div className="px-3 py-2 border-b border-border flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-indigo-500" />
        <span className="text-sm font-medium truncate">
          {data.agent?.name || data.label || "Agent"}
        </span>
      </div>
      <div className="px-3 py-2 text-xs text-muted-foreground">
        {data.agent?.role || "(unassigned)"}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className={HANDLE_CLASS}
      />
    </div>
  );
}

const nodeTypes = {
  start: StartNode,
  end: EndNode,
  agent: AgentNode,
};

function toFlowNodes(
  graph: WorkflowGraph,
  agents: Agent[],
): Node<CanvasNodeData>[] {
  const agentById = new Map(agents.map((a) => [a.id, a]));
  return graph.nodes.map((n, idx) => {
    const fallbackPos = { x: 100 + idx * (NODE_WIDTH + 80), y: 120 };
    const position = n.position ?? fallbackPos;
    const data: CanvasNodeData = {
      nodeKind: n.type,
      agent_id: n.agent_id,
      agent:
        n.type === "agent" && n.agent_id !== undefined
          ? agentById.get(n.agent_id) ?? null
          : null,
    };
    return {
      id: n.id,
      type: n.type,
      position,
      data,
    };
  });
}

function toFlowEdges(graph: WorkflowGraph): Edge[] {
  return graph.edges.map((e, i) => {
    const source = e.source ?? e.from ?? "";
    const target = e.target ?? e.to ?? "";
    return {
      id: e.id ?? `e-${source}-${target}-${i}`,
      source,
      target,
      label: e.when,
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 4,
      labelBgStyle: { fill: "#f5f5f5" },
      markerEnd: { type: MarkerType.ArrowClosed },
      data: { when: e.when ?? "" },
    };
  });
}

export function WorkflowCanvas({
  initialGraph,
  agents,
  onChange,
  onSelectionChange,
}: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNodeData>(
    toFlowNodes(initialGraph, agents),
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    toFlowEdges(initialGraph),
  );

  // Refresh nodes when agents list changes (so labels stay synced).
  React.useEffect(() => {
    setNodes((current) => {
      const agentById = new Map(agents.map((a) => [a.id, a]));
      return current.map((n) => {
        if (n.data.nodeKind !== "agent") return n;
        const aid = n.data.agent_id;
        const agent = aid !== undefined ? agentById.get(aid) ?? null : null;
        return { ...n, data: { ...n.data, agent } };
      });
    });
  }, [agents, setNodes]);

  // Emit graph JSON whenever nodes/edges change.
  React.useEffect(() => {
    if (!onChange) return;
    const graphNodes: GraphNode[] = nodes.map((n) => ({
      id: n.id,
      type: (n.type as GraphNode["type"]) ?? "agent",
      agent_id: n.data.agent_id,
      position: { x: n.position.x, y: n.position.y },
    }));
    const graphEdges: GraphEdge[] = edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      when: (e.data?.when as string | undefined) || undefined,
    }));
    onChange({ nodes: graphNodes, edges: graphEdges });
  }, [nodes, edges, onChange]);

  const handleConnect = React.useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            id: `e_${connection.source}_${connection.target}_${Date.now()}`,
            markerEnd: { type: MarkerType.ArrowClosed },
            data: { when: "" },
          },
          eds,
        ),
      );
    },
    [setEdges],
  );

  const handleSelectionChange = React.useCallback(
    (params: OnSelectionChangeParams) => {
      const node = (params.nodes[0] as Node<CanvasNodeData> | undefined) ?? null;
      const edge = (params.edges[0] as Edge | undefined) ?? null;
      onSelectionChange?.({ node, edge });
    },
    [onSelectionChange],
  );

  // Imperative API to mutate selected node/edge (used by parent inspector).
  React.useEffect(() => {
    canvasApi.setNodes = setNodes;
    canvasApi.setEdges = setEdges;
  }, [setNodes, setEdges]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onSelectionChange={handleSelectionChange}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="#e5e7eb" />
        <Controls position="bottom-left" showInteractive={false} />
        <MiniMap pannable zoomable className="!bg-card" />
      </ReactFlow>
    </div>
  );
}

// Small imperative bridge so parents can mutate the canvas after construction
// (e.g. from the NodeInspector or palette buttons) without prop-drilling setters.
export const canvasApi: {
  setNodes?: React.Dispatch<React.SetStateAction<Node<CanvasNodeData>[]>>;
  setEdges?: React.Dispatch<React.SetStateAction<Edge[]>>;
} = {};

export function addAgentNode(agent: Agent) {
  if (!canvasApi.setNodes) return;
  const id = `agent_${agent.id}_${Date.now().toString(36)}`;
  canvasApi.setNodes((nds) => [
    ...nds,
    {
      id,
      type: "agent",
      position: { x: 240 + nds.length * 40, y: 180 + nds.length * 40 },
      data: { nodeKind: "agent", agent_id: agent.id, agent },
    },
  ]);
}

export function addStartNode() {
  if (!canvasApi.setNodes) return;
  canvasApi.setNodes((nds) => {
    if (nds.some((n) => n.type === "start")) return nds;
    return [
      ...nds,
      {
        id: "start",
        type: "start",
        position: { x: 80, y: 80 },
        data: { nodeKind: "start" },
      },
    ];
  });
}

export function addEndNode() {
  if (!canvasApi.setNodes) return;
  canvasApi.setNodes((nds) => {
    if (nds.some((n) => n.type === "end")) return nds;
    return [
      ...nds,
      {
        id: "end",
        type: "end",
        position: { x: 600, y: 80 },
        data: { nodeKind: "end" },
      },
    ];
  });
}

export function deleteNode(id: string) {
  if (!canvasApi.setNodes || !canvasApi.setEdges) return;
  canvasApi.setNodes((nds) => nds.filter((n) => n.id !== id));
  canvasApi.setEdges((eds) =>
    eds.filter((e) => e.source !== id && e.target !== id),
  );
}

export function deleteEdge(id: string) {
  canvasApi.setEdges?.((eds) => eds.filter((e) => e.id !== id));
}

export function updateAgentNodeAgent(nodeId: string, agent: Agent) {
  canvasApi.setNodes?.((nds) =>
    nds.map((n) =>
      n.id === nodeId
        ? {
            ...n,
            data: {
              ...n.data,
              agent_id: agent.id,
              agent,
            },
          }
        : n,
    ),
  );
}

export function renameNode(nodeId: string, label: string) {
  canvasApi.setNodes?.((nds) =>
    nds.map((n) =>
      n.id === nodeId ? { ...n, data: { ...n.data, label } } : n,
    ),
  );
}

export function updateEdgeWhen(edgeId: string, when: string) {
  canvasApi.setEdges?.((eds) =>
    eds.map((e) =>
      e.id === edgeId
        ? {
            ...e,
            label: when || undefined,
            data: { ...(e.data ?? {}), when },
          }
        : e,
    ),
  );
}
