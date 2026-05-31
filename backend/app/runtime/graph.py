"""Compile a workflow JSON description into an executable LangGraph.

The JSON shape (also returned by the API) is:

    {
      "nodes": [
        {"id": "start", "type": "start"},
        {"id": "n1",    "type": "agent", "agent_id": 1},
        {"id": "end",   "type": "end"}
      ],
      "edges": [
        {"id": "e1", "source": "start", "target": "n1"},
        {"id": "e2", "source": "n1", "target": "end", "when": "label == 'bug'"}
      ]
    }

Conditional edges: when multiple outgoing edges from the same source have a
`when` expression, we register an `add_conditional_edges` mapping. The
`when` expression is evaluated with a restricted `eval` (no builtins) against
the current state — so the only names available are state keys like `label`,
`output`, `input`, etc.
"""
from __future__ import annotations

import logging
import operator
from typing import Annotated, Any, Callable, TypedDict

from asteval import Interpreter
from langgraph.graph import END, START, StateGraph

from ..models import Agent
from .agent_node import run_agent

logger = logging.getLogger(__name__)


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str | None, str | None]:
    source = edge.get("source") or edge.get("from")
    target = edge.get("target") or edge.get("to")
    return source, target


def _take_latest(_old: Any, new: Any) -> Any:
    """Reducer for scalar keys written by parallel branches.

    On fan-in (multiple predecessors finishing in the same super-step) LangGraph
    applies the reducer pairwise. We keep the most recent non-None write. The
    order among truly-concurrent branches is arbitrary, which is fine: downstream
    agents read the full accumulated `messages` list for context, not this scalar.
    """
    return new if new is not None else _old


class GraphState(TypedDict, total=False):
    # `messages` accumulates one entry per agent across the whole run. The
    # operator.add reducer lets parallel branches append concurrently — so each
    # node MUST return only its *new* messages, never the full list.
    messages: Annotated[list, operator.add]
    context: dict
    label: Annotated[str | None, _take_latest]
    input: str
    output: Annotated[str | None, _take_latest]
    last_agent: Annotated[str | None, _take_latest]


def _safe_eval(expr: str, state: dict[str, Any]) -> bool:
    """Evaluate a when-expression against state using restricted asteval."""
    if not expr or not expr.strip():
        return True
    aeval = Interpreter(use_numpy=False)
    for key, value in state.items():
        aeval.symtable[key] = value
    try:
        result = aeval(expr)
        if aeval.error:
            return False
        return bool(result)
    except Exception as exc:
        logger.warning("when-expr eval failed (%r): %s", expr, exc)
        return False


def _make_agent_fn(agent: Agent, run_id: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _fn(state: dict[str, Any]) -> dict[str, Any]:
        return run_agent(agent, state, run_id)

    _fn.__name__ = f"agent_{agent.id}_{agent.name}"
    return _fn


def _make_start_fn() -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _fn(state: dict[str, Any]) -> dict[str, Any]:
        # Pass-through: just ensures `input` is present and seeds context.
        # Do NOT return `messages` — the add-reducer would duplicate it.
        return {
            "context": state.get("context") or {},
            "input": state.get("input") or "",
        }

    _fn.__name__ = "start"
    return _fn


def _make_end_fn() -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _fn(state: dict[str, Any]) -> dict[str, Any]:
        return {"output": state.get("output") or ""}

    _fn.__name__ = "end"
    return _fn


def validate_graph(
    graph_json: dict[str, Any],
    agents_by_id: dict[int, Agent],
    strict: bool = True,
) -> None:
    """Raise ValueError if the graph is malformed.

    Two levels of validation:

    * Always (data integrity): node ids are unique and every edge references
      nodes that actually exist. These run on save so we never persist a
      structurally corrupt graph.
    * `strict=True` (run-time completeness): exactly one start, at least one
      end, start has an outgoing edge, end has an incoming edge, agent nodes
      are connected and reference a real agent. These would reject an
      in-progress draft, so they only run when the workflow is executed.
    """
    nodes = graph_json.get("nodes") or []
    edges = graph_json.get("edges") or []

    ids = {n.get("id") for n in nodes}
    if len(ids) != len(nodes):
        raise ValueError("duplicate node ids")

    for e in edges:
        src, tgt = _edge_endpoints(e)
        if src not in ids:
            raise ValueError(f"edge source '{src}' not in nodes")
        if tgt not in ids:
            raise ValueError(f"edge target '{tgt}' not in nodes")

    if not strict:
        return

    if not nodes:
        raise ValueError("graph has no nodes")

    types = [n.get("type") for n in nodes]
    if types.count("start") != 1:
        raise ValueError("graph must have exactly one start node")
    if types.count("end") < 1:
        raise ValueError("graph must have at least one end node")

    # Orphan agent nodes (no incoming or outgoing) are not allowed.
    sources = {_edge_endpoints(e)[0] for e in edges}
    targets = {_edge_endpoints(e)[1] for e in edges}
    for n in nodes:
        nid = n.get("id")
        ntype = n.get("type")
        if ntype == "start" and nid not in sources:
            raise ValueError(f"start node '{nid}' has no outgoing edge")
        if ntype == "end" and nid not in targets:
            raise ValueError(f"end node '{nid}' has no incoming edge")
        if ntype == "agent":
            if nid not in sources and nid not in targets:
                raise ValueError(f"orphan agent node '{nid}'")
            agent_id = n.get("agent_id")
            if agent_id is None or agent_id not in agents_by_id:
                raise ValueError(f"agent node '{nid}' references missing agent_id={agent_id}")


def build_graph(
    workflow_json: dict[str, Any],
    agents_by_id: dict[int, Agent],
    run_id: int,
) -> Any:
    """Compile workflow JSON into a LangGraph CompiledGraph for `run_id`."""
    validate_graph(workflow_json, agents_by_id)

    nodes = workflow_json.get("nodes") or []
    edges = workflow_json.get("edges") or []

    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in nodes}
    graph = StateGraph(GraphState)

    start_id: str = ""
    end_ids: set[str] = set()
    agent_node_ids: list[str] = []

    for node in nodes:
        nid = node["id"]
        ntype = node.get("type")
        if ntype == "start":
            start_id = nid
            graph.add_node(nid, _make_start_fn())
        elif ntype == "end":
            end_ids.add(nid)
            graph.add_node(nid, _make_end_fn())
        elif ntype == "agent":
            agent = agents_by_id[node["agent_id"]]
            graph.add_node(nid, _make_agent_fn(agent, run_id))
            agent_node_ids.append(nid)
        else:
            raise ValueError(f"unknown node type: {ntype}")

    graph.add_edge(START, start_id)
    for eid in end_ids:
        graph.add_edge(eid, END)

    # Group edges by source so we can decide unconditional vs conditional.
    by_source: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        src, _ = _edge_endpoints(e)
        if src:
            by_source.setdefault(src, []).append(e)

    for source, outs in by_source.items():
        conditional = [e for e in outs if e.get("when")]
        unconditional = [e for e in outs if not e.get("when")]

        if conditional:
            # Build a router that returns the matching target id (or a fallback).
            def _router(state: dict[str, Any], _outs=outs):
                for edge in _outs:
                    expr = edge.get("when")
                    _, tgt = _edge_endpoints(edge)
                    if expr and _safe_eval(expr, state) and tgt:
                        return tgt
                # Fallback to the first unconditional edge if present.
                for edge in _outs:
                    if not edge.get("when"):
                        _, tgt = _edge_endpoints(edge)
                        if tgt:
                            return tgt
                # As a final fallback, pick the first edge's target.
                _, tgt = _edge_endpoints(_outs[0])
                return tgt

            mapping = {
                tgt: tgt
                for edge in outs
                for tgt in [_edge_endpoints(edge)[1]]
                if tgt
            }
            graph.add_conditional_edges(source, _router, mapping)
        else:
            # Plain edges (possibly multiple, e.g. fan-out — LangGraph treats sequentially).
            for edge in unconditional:
                _, tgt = _edge_endpoints(edge)
                if tgt:
                    graph.add_edge(source, tgt)

    return graph.compile()


def compile_workflow_graph(workflow_graph: dict[str, Any], run_id: int) -> Any:
    """Load agents from DB and compile workflow JSON into a LangGraph."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Agent

    with Session(engine) as session:
        agents = session.exec(select(Agent)).all()
        agents_by_id = {a.id: a for a in agents if a.id is not None}
    return build_graph(workflow_graph, agents_by_id, run_id)
