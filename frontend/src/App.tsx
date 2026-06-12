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
import type { ChatMessage, GraphDto, GraphEdgeDto, GraphNodeDto } from "./types";

type ViewMode = "chat" | "graph";
type Point = {
  x: number;
  y: number;
};

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
  const codeNodes = useMemo(() => {
    return graph.nodes
      .filter(isVisibleCodeNode)
      .sort((left, right) => codeNodeRank(left) - codeNodeRank(right));
  }, [graph.nodes]);

  const visibleNodeIds = useMemo(() => {
    return new Set(codeNodes.map((node) => node.id));
  }, [codeNodes]);

  const nodes = useMemo<Node[]>(() => {
    const count = Math.max(codeNodes.length, 1);
    const columns = Math.max(2, Math.ceil(Math.sqrt(count)));
    const columnWidth = 250;
    const rowHeight = 116;
    return codeNodes.map((node, index) => {
      const column = index % columns;
      const row = Math.floor(index / columns);
      return {
        id: node.id,
        data: { label: graphNodeLabel(node) },
        position: {
          x: column * columnWidth,
          y: row * rowHeight,
        },
        className: `graph-node graph-node--${nodeKind(node).toLowerCase()}`,
      };
    });
  }, [codeNodes]);

  const edges = useMemo<Edge[]>(() => {
    return graph.edges
      .filter((edge) => isVisibleCodeEdge(edge))
      .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
      .map((edge, index) => ({
        id: `${edge.source}-${edge.type}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        animated: edge.type === "CALLS",
        className: `graph-edge graph-edge--${edge.type.toLowerCase()}`,
        data: { type: edge.type },
      }));
  }, [graph.edges, visibleNodeIds]);

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
          {nodes.length} Code-Knoten · {edges.length} Beziehungen
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

function graphNodeLabel(node: GraphNodeDto) {
  const kind = nodeKind(node);
  const title = truncate(String(node.label || node.properties.name || node.id), 32);
  const context = graphNodeContext(node);
  return (
    <div className="graph-node__content">
      <span className="graph-node__kind">{kindLabel(kind)}</span>
      <strong>{title}</strong>
      {context && <small>{context}</small>}
    </div>
  );
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

function isVisibleCodeNode(node: GraphNodeDto): boolean {
  if (node.labels.includes("ExternalImport") || node.labels.includes("Call")) {
    return false;
  }

  if (node.labels.includes("File")) {
    return true;
  }

  const kind = String(node.properties.kind || "");
  return ["package", "class", "object", "trait", "enum", "function"].includes(kind);
}

function isVisibleCodeEdge(edge: GraphEdgeDto): boolean {
  return ["DECLARES", "CALLS", "EXTENDS", "DEPENDS_ON", "INSTANTIATES"].includes(edge.type);
}

function codeNodeRank(node: GraphNodeDto): number {
  const order: Record<string, number> = {
    File: 0,
    package: 1,
    class: 2,
    object: 2,
    trait: 2,
    enum: 2,
    function: 3,
  };
  return order[nodeKind(node)] ?? 9;
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
