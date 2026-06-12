import {
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Panel,
  Position,
  type Edge,
  type Node,
} from "reactflow";
import {
  FolderOpen,
  GripHorizontal,
  Loader2,
  MessageSquare,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Send,
  Upload,
} from "lucide-react";
import { askQuestion, indexPath, loadGraph, uploadAndIndex } from "./api";
import type { ChatMessage, GraphDto, GraphNodeDto } from "./types";

type ViewMode = "chat" | "graph";
type Point = {
  x: number;
  y: number;
};
type UmlNodeModel = {
  id: string;
  kind: string;
  title: string;
  context: string;
  group: string;
  attributes: string[];
  methods: string[];
};
type UmlEdgeModel = {
  source: string;
  target: string;
  type: string;
  count: number;
};

const UML_CONTAINER_KINDS = new Set(["class", "object", "trait", "enum"]);
const UML_EDGE_TYPES = new Set(["CALLS", "EXTENDS", "INSTANTIATES", "USES"]);

const initialMessages: ChatMessage[] = [
  {
    id: crypto.randomUUID(),
    role: "assistant",
    text: "Welche Frage hast du zur indexierten Scala-Codebase?",
  },
];

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [question, setQuestion] = useState("");
  const [sourcePath, setSourcePath] = useState("testproject/Muehle");
  const [graph, setGraph] = useState<GraphDto>({ nodes: [], edges: [] });
  const [isAsking, setIsAsking] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [isGraphChatCollapsed, setIsGraphChatCollapsed] = useState(false);
  const [graphChatPosition, setGraphChatPosition] = useState<Point>({ x: 18, y: 18 });
  const [status, setStatus] = useState("Bereit");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const graphLayoutRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (fileInputRef.current) {
      fileInputRef.current.setAttribute("webkitdirectory", "");
      fileInputRef.current.setAttribute("directory", "");
    }
  }, []);

  useEffect(() => {
    if (viewMode === "graph" && graph.nodes.length === 0 && !isGraphLoading) {
      void refreshGraph();
    }
  }, [viewMode, graph.nodes.length, isGraphLoading]);

  async function handleIndexPath() {
    setIsIndexing(true);
    setStatus("Indexierung läuft");
    try {
      const response = await indexPath(sourcePath);
      setStatus(`Indexiert: ${response.source_path}`);
      await refreshGraph();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Indexierung fehlgeschlagen");
    } finally {
      setIsIndexing(false);
    }
  }

  async function handleFolderUpload(files: FileList | null) {
    if (!files || files.length === 0) {
      return;
    }
    setIsIndexing(true);
    setStatus("Upload und Indexierung laufen");
    try {
      const response = await uploadAndIndex(files);
      setStatus(`Indexiert: ${response.source_path}`);
      await refreshGraph();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Upload fehlgeschlagen");
    } finally {
      setIsIndexing(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function refreshGraph() {
    setIsGraphLoading(true);
    try {
      const nextGraph = await loadGraph();
      setGraph(nextGraph);
      setStatus(`Graph geladen: ${nextGraph.nodes.length} Knoten, ${nextGraph.edges.length} Kanten`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Graph konnte nicht geladen werden");
    } finally {
      setIsGraphLoading(false);
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isAsking) {
      return;
    }

    setQuestion("");
    setIsAsking(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: trimmedQuestion },
    ]);

    try {
      const response = await askQuestion(trimmedQuestion);
      const answer =
        response.answer ||
        response.snippets
          .slice(0, 3)
          .map((snippet) => snippet.text)
          .join("\n\n") ||
        "Keine passenden Snippets gefunden.";
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", text: answer },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "system",
          text: error instanceof Error ? error.message : "Anfrage fehlgeschlagen",
        },
      ]);
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <main
      className={
        viewMode === "graph"
          ? "app app--graph bg-coal-900 text-slate-100"
          : "app bg-coal-900 text-slate-100"
      }
    >
      <header className="topbar">
        <div className="brand">
          <Network size={22} />
          <span>Graphbased-AI</span>
        </div>
        <div className="topbar__actions">
          <span className="status">{status}</span>
          <button
            className="icon-button"
            onClick={() => void refreshGraph()}
            disabled={isGraphLoading}
            title="Graph aktualisieren"
          >
            {isGraphLoading ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
          </button>
          <button
            className="mode-button"
            onClick={() => setViewMode(viewMode === "chat" ? "graph" : "chat")}
          >
            {viewMode === "chat" ? <Network size={18} /> : <MessageSquare size={18} />}
            {viewMode === "chat" ? "Graph" : "Chat"}
          </button>
        </div>
      </header>

      {viewMode === "chat" ? (
        <section className="chat-layout">
          <ProjectPanel
            sourcePath={sourcePath}
            setSourcePath={setSourcePath}
            isIndexing={isIndexing}
            onIndexPath={handleIndexPath}
            onFolderClick={() => fileInputRef.current?.click()}
          />
          <ChatPanel
            messages={messages}
            question={question}
            setQuestion={setQuestion}
            isAsking={isAsking}
            onAsk={handleAsk}
            compact={false}
          />
        </section>
      ) : (
        <section ref={graphLayoutRef} className="graph-layout">
          <GraphCanvas graph={graph} />
          <GraphChatWindow
            collapsed={isGraphChatCollapsed}
            position={graphChatPosition}
            setCollapsed={setIsGraphChatCollapsed}
            setPosition={setGraphChatPosition}
            boundsRef={graphLayoutRef}
          >
            <ChatPanel
              messages={messages}
              question={question}
              setQuestion={setQuestion}
              isAsking={isAsking}
              onAsk={handleAsk}
              compact
            />
          </GraphChatWindow>
        </section>
      )}

      <input
        ref={fileInputRef}
        className="hidden-input"
        type="file"
        multiple
        onChange={(event) => void handleFolderUpload(event.currentTarget.files)}
      />
    </main>
  );
}

function GraphChatWindow(props: {
  collapsed: boolean;
  position: Point;
  setCollapsed: (value: boolean) => void;
  setPosition: (value: Point) => void;
  boundsRef: RefObject<HTMLElement>;
  children: ReactNode;
}) {
  const windowRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  function clampPosition(nextPosition: Point): Point {
    const bounds = props.boundsRef.current;
    const chatWindow = windowRef.current;
    const width = chatWindow?.offsetWidth ?? 410;
    const height = chatWindow?.offsetHeight ?? 520;
    const boundsWidth = bounds?.clientWidth ?? window.innerWidth;
    const boundsHeight = bounds?.clientHeight ?? window.innerHeight;
    const padding = 12;

    return {
      x: Math.min(Math.max(nextPosition.x, padding), Math.max(padding, boundsWidth - width - padding)),
      y: Math.min(Math.max(nextPosition.y, padding), Math.max(padding, boundsHeight - height - padding)),
    };
  }

  function handleDragStart(event: ReactPointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: props.position.x,
      originY: props.position.y,
    };
  }

  function handleDragMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }

    props.setPosition(
      clampPosition({
        x: drag.originX + event.clientX - drag.startX,
        y: drag.originY + event.clientY - drag.startY,
      }),
    );
  }

  function handleDragEnd(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <div
      ref={windowRef}
      className={props.collapsed ? "floating-chat floating-chat--collapsed" : "floating-chat"}
      style={{ transform: `translate(${props.position.x}px, ${props.position.y}px)` }}
    >
      <div
        className="floating-chat__titlebar"
        onPointerDown={handleDragStart}
        onPointerMove={handleDragMove}
        onPointerUp={handleDragEnd}
        onPointerCancel={handleDragEnd}
      >
        <span className="floating-chat__title">
          <GripHorizontal size={16} />
          <MessageSquare size={16} />
          Chat
        </span>
        <button
          className="floating-chat__collapse"
          type="button"
          title={props.collapsed ? "Chat ausklappen" : "Chat einklappen"}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => props.setCollapsed(!props.collapsed)}
        >
          {props.collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>
      {!props.collapsed && props.children}
    </div>
  );
}

function ProjectPanel(props: {
  sourcePath: string;
  setSourcePath: (value: string) => void;
  isIndexing: boolean;
  onIndexPath: () => void;
  onFolderClick: () => void;
}) {
  return (
    <aside className="project-panel">
      <div className="panel-title">Projekt</div>
      <label className="path-field">
        <span>Pfad</span>
        <input
          value={props.sourcePath}
          onChange={(event) => props.setSourcePath(event.target.value)}
          placeholder="/Users/name/project"
        />
      </label>
      <div className="project-actions">
        <button onClick={props.onIndexPath} disabled={props.isIndexing}>
          {props.isIndexing ? <Loader2 className="spin" size={18} /> : <FolderOpen size={18} />}
          Indexieren
        </button>
        <button
          className="secondary-button"
          onClick={props.onFolderClick}
          disabled={props.isIndexing}
          title="Ordner hochladen"
        >
          <Upload size={18} />
          Upload
        </button>
      </div>
    </aside>
  );
}

function ChatPanel(props: {
  messages: ChatMessage[];
  question: string;
  setQuestion: (value: string) => void;
  isAsking: boolean;
  onAsk: (event: FormEvent) => void;
  compact: boolean;
}) {
  return (
    <section className={props.compact ? "chat-panel chat-panel--compact" : "chat-panel"}>
      <div className="messages">
        {props.messages.map((message) => (
          <article key={message.id} className={`message message--${message.role}`}>
            <pre>{message.text}</pre>
          </article>
        ))}
        {props.isAsking && (
          <article className="message message--assistant">
            <Loader2 className="spin" size={18} />
          </article>
        )}
      </div>
      <form className="composer" onSubmit={props.onAsk}>
        <textarea
          value={props.question}
          onChange={(event) => props.setQuestion(event.target.value)}
          placeholder="Frage zur Codebase"
          rows={props.compact ? 2 : 3}
        />
        <button className="send-button" disabled={props.isAsking || !props.question.trim()}>
          <Send size={18} />
        </button>
      </form>
    </section>
  );
}

function GraphCanvas({ graph }: { graph: GraphDto }) {
  const nodeById = useMemo(() => {
    return new Map(graph.nodes.map((node) => [node.id, node]));
  }, [graph.nodes]);

  const umlModels = useMemo(() => buildUmlModels(graph.nodes), [graph.nodes]);

  const visibleUmlIds = useMemo(() => {
    return new Set(umlModels.map((node) => node.id));
  }, [umlModels]);

  const umlEdges = useMemo(() => {
    return buildUmlEdges(graph.edges, nodeById, visibleUmlIds);
  }, [graph.edges, nodeById, visibleUmlIds]);

  const nodes = useMemo<Node[]>(() => {
    return layoutUmlModels(umlModels, umlEdges).map(({ node, position }) => {
      return {
        id: node.id,
        data: { label: umlNodeLabel(node) },
        position,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        className: `graph-node graph-node--${node.kind.toLowerCase()}`,
      };
    });
  }, [umlModels, umlEdges]);

  const edges = useMemo<Edge[]>(() => {
    return umlEdges.map((edge, index) => ({
      id: `${edge.source}-${edge.type}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      label: edgeLabel(edge.type, edge.count),
      animated: edge.type === "CALLS",
      type: "smoothstep",
      className: `graph-edge graph-edge--${edge.type.toLowerCase()}`,
      data: { type: edge.type },
    }));
  }, [umlEdges]);

  return (
    <ReactFlow
      key={`${nodes.length}-${edges.length}`}
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.15}
      maxZoom={2}
    >
      <Background color="rgba(255, 255, 255, 0.12)" />
      <Controls position="bottom-right" />
      <MiniMap position="top-right" pannable zoomable />
      {nodes.length > 0 && (
        <Panel className="graph-summary-panel" position="top-center">
          {nodes.length} UML-Typen · {edges.length} Beziehungen
        </Panel>
      )}
      {nodes.length === 0 && (
        <Panel className="graph-empty-panel" position="top-center">
          Kein Graph geladen. Nutze das Reload-Symbol oben rechts oder indexiere ein Projekt.
        </Panel>
      )}
    </ReactFlow>
  );
}

function buildUmlModels(nodes: GraphNodeDto[]): UmlNodeModel[] {
  const containers = nodes
    .filter(isUmlContainerNode)
    .sort((left, right) => {
      const byKind = umlNodeRank(left) - umlNodeRank(right);
      if (byKind !== 0) {
        return byKind;
      }
      return String(left.label).localeCompare(String(right.label));
    });
  const methodsByParent = new Map<string, string[]>();
  const attributesByParent = new Map<string, string[]>();
  const methodsByContainer = new Map<string, GraphNodeDto[]>();

  nodes.forEach((node) => {
    const parentId = String(node.properties.parent_id || "");
    if (!parentId) {
      return;
    }

    if (nodeKind(node) === "function") {
      const methods = methodsByParent.get(parentId) ?? [];
      methods.push(formatMember(node, "method"));
      methodsByParent.set(parentId, methods);
      const methodNodes = methodsByContainer.get(parentId) ?? [];
      methodNodes.push(node);
      methodsByContainer.set(parentId, methodNodes);
    }
  });

  nodes.forEach((node) => {
    const parentId = String(node.properties.parent_id || "");
    if (!parentId) {
      return;
    }

    if (["val", "var", "enum_case"].includes(nodeKind(node)) && isClassLevelAttribute(node, methodsByContainer.get(parentId) ?? [])) {
      const attributes = attributesByParent.get(parentId) ?? [];
      attributes.push(formatMember(node, "attribute"));
      attributesByParent.set(parentId, attributes);
    }
  });

  return containers.map((node) => ({
    id: node.id,
    kind: nodeKind(node),
    title: truncate(String(node.label || node.properties.name || node.id), 34),
    context: graphNodeContext(node),
    group: umlGroup(node),
    attributes: sortMembers(attributesByParent.get(node.id) ?? []).slice(0, 8),
    methods: sortMembers(methodsByParent.get(node.id) ?? []).slice(0, 12),
  }));
}

function buildUmlEdges(
  graphEdges: GraphDto["edges"],
  nodeById: Map<string, GraphNodeDto>,
  visibleUmlIds: Set<string>,
): UmlEdgeModel[] {
  const edgeByKey = new Map<string, UmlEdgeModel>();

  graphEdges
    .filter((edge) => UML_EDGE_TYPES.has(edge.type))
    .forEach((edge) => {
      const source = ownerUmlNodeId(edge.source, nodeById);
      const target = ownerUmlNodeId(edge.target, nodeById);
      if (!source || !target || source === target) {
        return;
      }
      if (!visibleUmlIds.has(source) || !visibleUmlIds.has(target)) {
        return;
      }

      const key = `${source}-${edge.type}-${target}`;
      const existing = edgeByKey.get(key);
      if (existing) {
        existing.count += 1;
        return;
      }
      edgeByKey.set(key, { source, target, type: edge.type, count: 1 });
    });

  return Array.from(edgeByKey.values()).sort((left, right) => {
    const bySource = left.source.localeCompare(right.source);
    if (bySource !== 0) {
      return bySource;
    }
    const byTarget = left.target.localeCompare(right.target);
    if (byTarget !== 0) {
      return byTarget;
    }
    return left.type.localeCompare(right.type);
  });
}

function layoutUmlModels(
  models: UmlNodeModel[],
  edges: UmlEdgeModel[],
): Array<{ node: UmlNodeModel; position: Point }> {
  const modelById = new Map(models.map((model) => [model.id, model]));
  const connectedIds = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const groups = new Map<string, UmlNodeModel[]>();

  models.forEach((model) => {
    const groupModels = groups.get(model.group) ?? [];
    groupModels.push(model);
    groups.set(model.group, groupModels);
  });

  const orderedGroups = Array.from(groups.entries()).sort((left, right) => {
    const byRank = umlGroupRank(left[0]) - umlGroupRank(right[0]);
    if (byRank !== 0) {
      return byRank;
    }
    return left[0].localeCompare(right[0]);
  });

  const positions = new Map<string, Point>();
  const columnWidth = 380;
  const rowGap = 34;

  orderedGroups.forEach(([group, groupModels], column) => {
    const incomingById = incomingWeightById(groupModels, edges);
    const outgoingById = outgoingWeightById(groupModels, edges);
    const sortedModels = [...groupModels].sort((left, right) => {
      const leftConnected = connectedIds.has(left.id) ? 0 : 1;
      const rightConnected = connectedIds.has(right.id) ? 0 : 1;
      if (leftConnected !== rightConnected) {
        return leftConnected - rightConnected;
      }
      const byKind = umlKindRank(left.kind) - umlKindRank(right.kind);
      if (byKind !== 0) {
        return byKind;
      }
      const byTraffic =
        (incomingById.get(right.id) ?? 0) +
        (outgoingById.get(right.id) ?? 0) -
        ((incomingById.get(left.id) ?? 0) + (outgoingById.get(left.id) ?? 0));
      if (byTraffic !== 0) {
        return byTraffic;
      }
      return left.title.localeCompare(right.title);
    });

    let y = 0;
    sortedModels.forEach((model) => {
      positions.set(model.id, {
        x: column * columnWidth,
        y,
      });
      y += estimateUmlNodeHeight(model) + rowGap;
    });

    if (group && sortedModels.length > 0) {
      const groupOffset = umlGroupRank(group) % 2 === 0 ? 0 : 36;
      sortedModels.forEach((model) => {
        const position = positions.get(model.id);
        if (position) {
          position.y += groupOffset;
        }
      });
    }
  });

  return models.map((node) => ({
    node,
    position: positions.get(node.id) ?? { x: 0, y: 0 },
  }));
}

function umlNodeLabel(node: UmlNodeModel) {
  return (
    <div className="uml-node">
      <header className="uml-node__header">
        <span className="graph-node__kind">{kindLabel(node.kind)}</span>
        <strong>{node.title}</strong>
        {node.context && <small>{node.context}</small>}
      </header>
      <section className="uml-node__section">
        {node.attributes.length > 0 ? (
          node.attributes.map((attribute) => <span key={attribute}>{attribute}</span>)
        ) : (
          <span className="uml-node__empty">keine Felder</span>
        )}
      </section>
      <section className="uml-node__section uml-node__section--methods">
        {node.methods.length > 0 ? (
          node.methods.map((method) => <span key={method}>{method}</span>)
        ) : (
          <span className="uml-node__empty">keine Methoden</span>
        )}
      </section>
    </div>
  );
}

function estimateUmlNodeHeight(node: UmlNodeModel): number {
  const headerHeight = node.context ? 76 : 58;
  const attributeRows = Math.max(1, node.attributes.length);
  const methodRows = Math.max(1, node.methods.length);
  return headerHeight + attributeRows * 17 + methodRows * 17 + 54;
}

function incomingWeightById(models: UmlNodeModel[], edges: UmlEdgeModel[]): Map<string, number> {
  const ids = new Set(models.map((model) => model.id));
  const weights = new Map<string, number>();
  edges.forEach((edge) => {
    if (ids.has(edge.target)) {
      weights.set(edge.target, (weights.get(edge.target) ?? 0) + edge.count);
    }
  });
  return weights;
}

function outgoingWeightById(models: UmlNodeModel[], edges: UmlEdgeModel[]): Map<string, number> {
  const ids = new Set(models.map((model) => model.id));
  const weights = new Map<string, number>();
  edges.forEach((edge) => {
    if (ids.has(edge.source)) {
      weights.set(edge.source, (weights.get(edge.source) ?? 0) + edge.count);
    }
  });
  return weights;
}

function nodeKind(node: GraphNodeDto): string {
  if (node.labels.includes("File")) {
    return "File";
  }
  if (node.labels.includes("ExternalImport")) {
    return "External";
  }
  if (node.labels.includes("Call")) {
    return "Call";
  }
  return String(node.properties.kind || "Symbol");
}

function isUmlContainerNode(node: GraphNodeDto): boolean {
  return UML_CONTAINER_KINDS.has(nodeKind(node));
}

function umlNodeRank(node: GraphNodeDto): number {
  const order: Record<string, number> = {
    trait: 0,
    class: 1,
    object: 2,
    enum: 3,
  };
  return order[nodeKind(node)] ?? 9;
}

function umlKindRank(kind: string): number {
  const order: Record<string, number> = {
    trait: 0,
    class: 1,
    object: 2,
    enum: 3,
  };
  return order[kind] ?? 9;
}

function umlGroup(node: GraphNodeDto): string {
  const sourcePath = String(node.properties.source_path || node.properties.path || "");
  const fqn = String(node.properties.fqn || "");
  const value = `${sourcePath}/${fqn}`.toLowerCase();

  if (value.includes("/src/test/") || value.includes(".spec")) {
    return "Tests";
  }
  if (value.includes("/util/") || value.includes(".util.")) {
    return "Util";
  }
  if (value.includes("/model/") || value.includes(".model.")) {
    return "Model";
  }
  if (value.includes("/controller/") || value.includes(".controller.")) {
    return "Controller";
  }
  if (value.includes("/aview/") || value.includes(".aview.") || value.includes("/view/")) {
    return "View";
  }
  if (value.includes("/fileio") || value.includes(".fileio")) {
    return "IO";
  }
  return "Core";
}

function umlGroupRank(group: string): number {
  const order: Record<string, number> = {
    Util: 0,
    Model: 1,
    Controller: 2,
    View: 3,
    IO: 4,
    Core: 5,
    Tests: 6,
  };
  return order[group] ?? 99;
}

function kindLabel(kind: string): string {
  const labels: Record<string, string> = {
    File: "Datei",
    package: "Package",
    class: "Class",
    object: "Object",
    trait: "Trait",
    enum: "Enum",
    function: "Function",
  };
  return labels[kind] ?? "Code";
}

function graphNodeContext(node: GraphNodeDto): string {
  const sourcePath = String(node.properties.source_path || node.properties.path || "");
  if (sourcePath) {
    return compactPath(sourcePath);
  }

  const fqn = String(node.properties.fqn || "");
  if (fqn && fqn !== node.label) {
    return truncate(fqn, 42);
  }

  return "";
}

function ownerUmlNodeId(nodeId: string, nodeById: Map<string, GraphNodeDto>): string | null {
  const node = nodeById.get(nodeId);
  if (!node) {
    return null;
  }
  if (isUmlContainerNode(node)) {
    return node.id;
  }

  const parentId = String(node.properties.parent_id || "");
  const parent = parentId ? nodeById.get(parentId) : null;
  if (parent && isUmlContainerNode(parent)) {
    return parent.id;
  }

  return null;
}

function formatMember(node: GraphNodeDto, type: "attribute" | "method"): string {
  const name = String(node.properties.name || node.label || node.id);
  const metadata = parseMetadata(node.properties.metadata_json);
  if (type === "method") {
    const parameters = typeof metadata.parameters === "string" ? metadata.parameters : "()";
    const returnType = typeof metadata.return_type === "string" ? `: ${metadata.return_type}` : "";
    return `+ ${truncate(name, 26)}${truncate(parameters, 36)}${returnType}`;
  }

  const prefix = nodeKind(node) === "var" ? "~" : "+";
  const valueType = typeof metadata.type === "string" ? `: ${metadata.type}` : "";
  return `${prefix} ${truncate(name, 34)}${valueType}`;
}

function isClassLevelAttribute(node: GraphNodeDto, siblingMethods: GraphNodeDto[]): boolean {
  if (nodeKind(node) === "enum_case") {
    return true;
  }

  const startByte = numericProperty(node.properties.start_byte);
  if (startByte === null) {
    return true;
  }

  return !siblingMethods.some((method) => {
    const methodStart = numericProperty(method.properties.start_byte);
    const methodEnd = numericProperty(method.properties.end_byte);
    return methodStart !== null && methodEnd !== null && startByte > methodStart && startByte < methodEnd;
  });
}

function numericProperty(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parseMetadata(value: unknown): Record<string, unknown> {
  if (typeof value !== "string" || !value) {
    return {};
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function sortMembers(members: string[]): string[] {
  return [...members].sort((left, right) => left.localeCompare(right));
}

function edgeLabel(type: string, count: number): string {
  const labels: Record<string, string> = {
    CALLS: "calls",
    EXTENDS: "extends",
    INSTANTIATES: "creates",
    USES: "uses",
  };
  const label = labels[type] ?? type.toLowerCase();
  return count > 1 ? `${label} (${count})` : label;
}

function compactPath(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 3) {
    return path;
  }
  return parts.slice(-3).join("/");
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}

export default App;
