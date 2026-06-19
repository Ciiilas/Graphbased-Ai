import {
  type FormEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  type Edge,
  type Node,
} from "reactflow";
import {
  FolderOpen,
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
type GraphDisplayMode = "layers" | "uml";
type GraphClassDetailMode = "compact" | "uml";
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
type LayerNodeModel = {
  id: string;
  group: string;
  typeCount: number;
  attributeCount: number;
  methodCount: number;
};
type LayerEdgeModel = {
  source: string;
  target: string;
  count: number;
};

const UML_CONTAINER_KINDS = new Set(["class", "object", "trait", "enum"]);
const UML_EDGE_TYPES = new Set(["CALLS", "EXTENDS", "INSTANTIATES", "USES"]);
const UML_EDGE_TYPE_OPTIONS = [
  { type: "CALLS", label: "Calls", color: "rgba(251, 146, 60, 0.82)" },
  { type: "USES", label: "Uses", color: "rgba(148, 163, 184, 0.74)" },
  { type: "EXTENDS", label: "Extends", color: "rgba(74, 222, 128, 0.7)" },
  { type: "INSTANTIATES", label: "Creates", color: "rgba(74, 222, 128, 0.7)" },
];
const DEFAULT_VISIBLE_EDGE_TYPES = new Set(["CALLS", "USES"]);

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
  const [status, setStatus] = useState("Bereit");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
        <section
          className={
            isGraphChatCollapsed
              ? "graph-layout graph-layout--chat-collapsed"
              : "graph-layout"
          }
        >
          <div className="graph-canvas-wrap">
            <GraphCanvas graph={graph} />
          </div>
          <GraphChatDock
            collapsed={isGraphChatCollapsed}
            setCollapsed={setIsGraphChatCollapsed}
          >
            <ChatPanel
              messages={messages}
              question={question}
              setQuestion={setQuestion}
              isAsking={isAsking}
              onAsk={handleAsk}
              compact
            />
          </GraphChatDock>
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

function GraphChatDock(props: {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
  children: ReactNode;
}) {
  if (props.collapsed) {
    return (
      <aside className="graph-chat-dock graph-chat-dock--collapsed">
        <button
          className="graph-chat-dock__rail"
          type="button"
          title="Chat ausklappen"
          onClick={() => props.setCollapsed(false)}
        >
          <PanelLeftOpen size={18} />
          <MessageSquare size={18} />
          <span className="graph-chat-dock__rail-label">Chat</span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="graph-chat-dock">
      <div className="graph-chat-dock__titlebar">
        <span className="graph-chat-dock__title">
          <MessageSquare size={16} />
          Chat
        </span>
        <button
          className="graph-chat-dock__collapse"
          type="button"
          title="Chat einklappen"
          onClick={() => props.setCollapsed(true)}
        >
          <PanelLeftClose size={16} />
        </button>
      </div>
      {props.children}
    </aside>
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
            <MessageText text={message.text} />
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

function MessageText({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: ReactNode[] = [];
  let paragraphLines: string[] = [];
  let bulletLines: string[] = [];

  function flushParagraph() {
    if (paragraphLines.length === 0) {
      return;
    }
    const key = `paragraph-${elements.length}`;
    elements.push(
      <p key={key}>
        {paragraphLines.map((line, lineIndex) => (
          <span key={`${key}-${lineIndex}`}>
            {lineIndex > 0 && <br />}
            {renderInlineMarkdown(line)}
          </span>
        ))}
      </p>,
    );
    paragraphLines = [];
  }

  function flushBullets() {
    if (bulletLines.length === 0) {
      return;
    }
    const key = `list-${elements.length}`;
    elements.push(
      <ul key={key}>
        {bulletLines.map((line, lineIndex) => (
          <li key={`${key}-${lineIndex}`}>{renderInlineMarkdown(line.replace(/^\s*[-*]\s+/, ""))}</li>
        ))}
      </ul>,
    );
    bulletLines = [];
  }

  lines.forEach((line) => {
    const trimmedLine = line.trim();
    if (!trimmedLine) {
      flushParagraph();
      flushBullets();
      return;
    }

    if (/^#{1,4}\s+/.test(trimmedLine)) {
      flushParagraph();
      flushBullets();
      elements.push(
        <h3 key={`heading-${elements.length}`} className="message-heading">
          {renderInlineMarkdown(trimmedLine.replace(/^#{1,4}\s+/, ""))}
        </h3>,
      );
      return;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph();
      bulletLines.push(line);
      return;
    }

    flushBullets();
    paragraphLines.push(line);
  });

  flushParagraph();
  flushBullets();

  return (
    <div className="message-content">
      {elements}
    </div>
  );
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*.+?\*\*)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(text.slice(cursor, match.index));
    }

    const token = match[0];
    const key = `${match.index}-${token}`;
    if (token.startsWith("`")) {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else {
      parts.push(<strong key={key}>{renderInlineMarkdown(token.slice(2, -2))}</strong>);
    }
    cursor = match.index + token.length;
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return parts;
}

function GraphCanvas({ graph }: { graph: GraphDto }) {
  const [displayMode, setDisplayMode] = useState<GraphDisplayMode>("layers");
  const [classDetailMode, setClassDetailMode] = useState<GraphClassDetailMode>("compact");
  const [expandedClassId, setExpandedClassId] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [activeEdgeTypes, setActiveEdgeTypes] = useState<Set<string>>(
    () => new Set(DEFAULT_VISIBLE_EDGE_TYPES),
  );
  const nodeById = useMemo(() => {
    return new Map(graph.nodes.map((node) => [node.id, node]));
  }, [graph.nodes]);

  const umlModels = useMemo(() => buildUmlModels(graph.nodes), [graph.nodes]);

  const layerModels = useMemo(() => buildLayerModels(umlModels), [umlModels]);

  const allUmlIds = useMemo(() => {
    return new Set(umlModels.map((node) => node.id));
  }, [umlModels]);

  const allUmlEdges = useMemo(() => {
    return buildUmlEdges(graph.edges, nodeById, allUmlIds);
  }, [graph.edges, nodeById, allUmlIds]);

  const filteredUmlEdges = useMemo(() => {
    return allUmlEdges.filter((edge) => activeEdgeTypes.has(edge.type));
  }, [activeEdgeTypes, allUmlEdges]);

  const selectedGroupExists = useMemo(() => {
    return selectedGroup !== null && layerModels.some((layer) => layer.group === selectedGroup);
  }, [layerModels, selectedGroup]);

  useEffect(() => {
    if (selectedGroup !== null && !selectedGroupExists) {
      setSelectedGroup(null);
      setDisplayMode("layers");
    }
  }, [selectedGroup, selectedGroupExists]);

  const neighborIds = useMemo(() => {
    if (displayMode !== "uml" || selectedGroup === null) {
      return new Set<string>();
    }
    const members = new Set(
      umlModels.filter((node) => node.group === selectedGroup).map((node) => node.id),
    );
    const result = new Set<string>();
    filteredUmlEdges.forEach((edge) => {
      if (members.has(edge.source) && !members.has(edge.target)) {
        result.add(edge.target);
      }
      if (members.has(edge.target) && !members.has(edge.source)) {
        result.add(edge.source);
      }
    });
    return result;
  }, [displayMode, filteredUmlEdges, selectedGroup, umlModels]);

  const visibleUmlModels = useMemo(() => {
    if (displayMode !== "uml" || selectedGroup === null) {
      return umlModels;
    }
    return umlModels.filter(
      (node) => node.group === selectedGroup || neighborIds.has(node.id),
    );
  }, [displayMode, neighborIds, selectedGroup, umlModels]);

  const visibleUmlIds = useMemo(() => {
    return new Set(visibleUmlModels.map((node) => node.id));
  }, [visibleUmlModels]);

  const visibleUmlEdges = useMemo(() => {
    return filteredUmlEdges.filter((edge) => visibleUmlIds.has(edge.source) && visibleUmlIds.has(edge.target));
  }, [filteredUmlEdges, visibleUmlIds]);

  // Die Layer-Uebersicht zeigt bewusst alle Beziehungstypen; der Typ-Filter
  // wirkt nur in der Klassen-Sicht.
  const layerEdges = useMemo(() => {
    return buildLayerEdges(allUmlEdges, umlModels);
  }, [allUmlEdges, umlModels]);

  const nodes = useMemo<Node[]>(() => {
    if (displayMode === "layers") {
      return layoutLayerModels(layerModels).map(({ node, position }) => ({
        id: node.id,
        data: { label: layerNodeLabel(node) },
        position,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        className: `graph-node graph-node--layer graph-node--layer-${node.group.toLowerCase()}`,
      }));
    }

    return layoutUmlModels(visibleUmlModels, visibleUmlEdges, classDetailMode, expandedClassId).map(({ node, position }) => {
      const isExpanded = classDetailMode === "compact" && node.id === expandedClassId;
      const neighborClass = neighborIds.has(node.id) && !isExpanded ? " graph-node--neighbor" : "";
      const detail: GraphClassDetailMode = isExpanded ? "uml" : classDetailMode;
      const expandedClass = isExpanded ? " graph-node--expanded" : "";
      return {
        id: node.id,
        data: { label: detail === "compact" ? compactUmlNodeLabel(node) : umlNodeLabel(node) },
        position,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        className: `graph-node graph-node--${node.kind.toLowerCase()} graph-node--${detail}${neighborClass}${expandedClass}`,
      };
    });
  }, [classDetailMode, displayMode, expandedClassId, layerModels, neighborIds, visibleUmlEdges, visibleUmlModels]);

  const edges = useMemo<Edge[]>(() => {
    if (displayMode === "layers") {
      return layerEdges.map((edge, index) => ({
        id: `${edge.source}-layer-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        label: layerEdgeLabel(edge.count),
        animated: false,
        type: "smoothstep",
        className: "graph-edge graph-edge--layer",
        markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(251, 146, 60, 0.68)" },
        style: { strokeWidth: layerEdgeWidth(edge.count), opacity: 0.72 },
      }));
    }

    return visibleUmlEdges.map((edge, index) => ({
      id: `${edge.source}-${edge.type}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      label: edgeLabel(edge.type, edge.count),
      animated: edge.type === "CALLS",
      type: "smoothstep",
      className: `graph-edge graph-edge--${edge.type.toLowerCase()}`,
      markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(148, 163, 184, 0.85)" },
      data: { type: edge.type },
    }));
  }, [displayMode, layerEdges, visibleUmlEdges]);

  function showLayerDetails(group: string) {
    setSelectedGroup(group);
    setClassDetailMode("compact");
    setExpandedClassId(null);
    setDisplayMode("uml");
  }

  function showAllClasses() {
    setSelectedGroup(null);
    setClassDetailMode("compact");
    setExpandedClassId(null);
    setDisplayMode("uml");
  }

  function showLayerOverview() {
    setSelectedGroup(null);
    setExpandedClassId(null);
    setDisplayMode("layers");
  }

  function changeClassDetailMode(mode: GraphClassDetailMode) {
    setClassDetailMode(mode);
    setExpandedClassId(null);
  }

  function toggleEdgeType(edgeType: string) {
    setActiveEdgeTypes((current) => {
      const next = new Set(current);
      if (next.has(edgeType)) {
        next.delete(edgeType);
      } else {
        next.add(edgeType);
      }
      return next.size > 0 ? next : current;
    });
  }

  return (
    <ReactFlow
      key={`${displayMode}-${classDetailMode}-${selectedGroup ?? "all"}-${expandedClassId ?? "none"}-${nodes.length}-${edges.length}`}
      nodes={nodes}
      edges={edges}
      onNodeClick={(_, node) => {
        if (displayMode === "layers") {
          showLayerDetails(String(node.id).replace(/^layer:/, ""));
          return;
        }
        if (classDetailMode === "compact") {
          const id = String(node.id);
          setExpandedClassId((current) => (current === id ? null : id));
        }
      }}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.15}
      maxZoom={2}
    >
      <Background color="rgba(255, 255, 255, 0.12)" />
      <Controls position="bottom-right" />
      <MiniMap position="top-right" pannable zoomable />
      {umlModels.length > 0 && (
        <Panel className="graph-mode-panel" position="top-left">
          <button
            className={displayMode === "layers" ? "graph-mode-button graph-mode-button--active" : "graph-mode-button"}
            type="button"
            onClick={showLayerOverview}
          >
            MVC
          </button>
          <button
            className={
              displayMode === "uml" && selectedGroup === null
                ? "graph-mode-button graph-mode-button--active"
                : "graph-mode-button"
            }
            type="button"
            onClick={showAllClasses}
          >
            Klassen
          </button>
          {displayMode === "uml" && (
            <span className="graph-detail-switch" aria-label="Klassendarstellung">
              <button
                className={
                  classDetailMode === "compact"
                    ? "graph-chip graph-chip--active"
                    : "graph-chip"
                }
                type="button"
                onClick={() => changeClassDetailMode("compact")}
              >
                Kompakt
              </button>
              <button
                className={
                  classDetailMode === "uml"
                    ? "graph-chip graph-chip--active"
                    : "graph-chip"
                }
                type="button"
                onClick={() => changeClassDetailMode("uml")}
              >
                UML
              </button>
            </span>
          )}
          {displayMode === "uml" && (
            <span className="graph-edge-filter" aria-label="Beziehungstypen">
              {UML_EDGE_TYPE_OPTIONS.map((option) => (
                <button
                  key={option.type}
                  className={
                    activeEdgeTypes.has(option.type)
                      ? "graph-chip graph-chip--active"
                      : "graph-chip"
                  }
                  type="button"
                  onClick={() => toggleEdgeType(option.type)}
                >
                  <span className="graph-chip__dot" style={{ background: option.color }} />
                  {option.label}
                </button>
              ))}
            </span>
          )}
          {selectedGroup && (
            <span className="graph-breadcrumb">
              <button
                className="graph-breadcrumb__link"
                type="button"
                onClick={showLayerOverview}
              >
                MVC
              </button>
              <span className="graph-breadcrumb__sep">›</span>
              <span className="graph-breadcrumb__current">{selectedGroup}</span>
            </span>
          )}
        </Panel>
      )}
      {nodes.length > 0 && (
        <Panel className="graph-summary-panel" position="bottom-center">
          {displayMode === "layers"
            ? `${nodes.length} Layer - ${edges.length} Beziehungen`
            : selectedGroup
              ? `${selectedGroup}: ${nodes.length} UML-Typen - ${edges.length} Beziehungen`
              : `${nodes.length} UML-Typen - ${edges.length} Beziehungen`}
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

function buildLayerModels(models: UmlNodeModel[]): LayerNodeModel[] {
  const layerByGroup = new Map<string, LayerNodeModel>();

  models.forEach((model) => {
    const layer = layerByGroup.get(model.group) ?? {
      id: `layer:${model.group}`,
      group: model.group,
      typeCount: 0,
      attributeCount: 0,
      methodCount: 0,
    };
    layer.typeCount += 1;
    layer.attributeCount += model.attributes.length;
    layer.methodCount += model.methods.length;
    layerByGroup.set(model.group, layer);
  });

  return Array.from(layerByGroup.values()).sort((left, right) => {
    const byRank = umlGroupRank(left.group) - umlGroupRank(right.group);
    if (byRank !== 0) {
      return byRank;
    }
    return left.group.localeCompare(right.group);
  });
}

function buildLayerEdges(edges: UmlEdgeModel[], models: UmlNodeModel[]): LayerEdgeModel[] {
  const groupByNodeId = new Map(models.map((model) => [model.id, model.group]));
  const edgeByKey = new Map<string, LayerEdgeModel>();

  edges.forEach((edge) => {
    const sourceGroup = groupByNodeId.get(edge.source);
    const targetGroup = groupByNodeId.get(edge.target);
    if (!sourceGroup || !targetGroup || sourceGroup === targetGroup) {
      return;
    }

    const source = `layer:${sourceGroup}`;
    const target = `layer:${targetGroup}`;
    const key = `${source}->${target}`;
    const existing = edgeByKey.get(key);
    if (existing) {
      existing.count += edge.count;
      return;
    }
    edgeByKey.set(key, { source, target, count: edge.count });
  });

  return Array.from(edgeByKey.values()).sort((left, right) => {
    const leftSource = left.source.replace(/^layer:/, "");
    const rightSource = right.source.replace(/^layer:/, "");
    const bySource = umlGroupRank(leftSource) - umlGroupRank(rightSource);
    if (bySource !== 0) {
      return bySource;
    }
    const leftTarget = left.target.replace(/^layer:/, "");
    const rightTarget = right.target.replace(/^layer:/, "");
    const byTarget = umlGroupRank(leftTarget) - umlGroupRank(rightTarget);
    if (byTarget !== 0) {
      return byTarget;
    }
    return left.target.localeCompare(right.target);
  });
}

// Architektonisch sinnvolle Anordnung: MVC-Fluss View -> Controller -> Model
// auf der mittleren Zeile, Stuetzschichten darueber/darunter.
const LAYER_LAYOUT: Record<string, Point> = {
  View: { x: 0, y: 0 },
  Controller: { x: 1, y: 0 },
  Model: { x: 2, y: 0 },
  IO: { x: 2, y: 1 },
  Util: { x: 1, y: 1 },
  Core: { x: 1, y: -1 },
  Tests: { x: 3, y: -1 },
};

function layoutLayerModels(
  models: LayerNodeModel[],
): Array<{ node: LayerNodeModel; position: Point }> {
  const columnWidth = 440;
  const rowHeight = 240;
  const fallbackRowOffset = 86;

  return models.map((node, index) => {
    const cell = LAYER_LAYOUT[node.group];
    const position = cell
      ? { x: cell.x * columnWidth, y: cell.y * rowHeight }
      : { x: index * columnWidth, y: index % 2 === 0 ? 0 : fallbackRowOffset };
    return { node, position };
  });
}

function layerNodeLabel(node: LayerNodeModel) {
  return (
    <div className="layer-node">
      <span className="graph-node__kind">Layer</span>
      <strong>{node.group}</strong>
      <div className="layer-node__stats">
        <span>{node.typeCount} Typen</span>
        <span>{node.attributeCount} Felder</span>
        <span>{node.methodCount} Methoden</span>
      </div>
    </div>
  );
}

function layoutUmlModels(
  models: UmlNodeModel[],
  edges: UmlEdgeModel[],
  detailMode: GraphClassDetailMode,
  expandedId: string | null,
): Array<{ node: UmlNodeModel; position: Point }> {
  // Effektiver Darstellungsmodus eines Knotens: ein im Kompaktmodus
  // aufgeklappter Knoten wird wie ein voller UML-Knoten behandelt.
  const detailOf = (id: string): GraphClassDetailMode =>
    detailMode === "compact" && id === expandedId ? "uml" : detailMode;
  const hasExpanded = detailMode === "compact" && expandedId !== null && models.some((model) => model.id === expandedId);
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
  // Kompakte Spalten sind eng; ein aufgeklappter (voller) Knoten braucht mehr
  // Breite, daher die Spalte nur dann aufweiten.
  const columnWidth = detailMode === "compact" ? (hasExpanded ? 300 : 260) : 380;
  const rowGap = detailMode === "compact" ? 22 : 34;

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
      y += estimateUmlNodeHeight(model, detailOf(model.id)) + rowGap;
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

function compactUmlNodeLabel(node: UmlNodeModel) {
  return (
    <div className="compact-node">
      <span className="graph-node__kind">{kindLabel(node.kind)}</span>
      <strong>{node.title}</strong>
      {node.context && <small>{node.context}</small>}
      <span className="compact-node__meta">
        {node.attributes.length} Felder · {node.methods.length} Methoden
      </span>
    </div>
  );
}

function estimateUmlNodeHeight(node: UmlNodeModel, detailMode: GraphClassDetailMode): number {
  if (detailMode === "compact") {
    return node.context ? 104 : 88;
  }
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

function layerEdgeLabel(count: number): string {
  return `${count}x`;
}

function layerEdgeWidth(count: number): number {
  return Math.min(1.4 + Math.log2(count + 1) * 0.9, 5.5);
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
