import { useState, useMemo, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  Position,
  MarkerType,
  useNodesState,
  useEdgesState,
  Panel,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useResourceGraph } from '../hooks/useResourceGraph';
import type { GraphNode, GraphFilters } from '../types/graph';
import { SERVICE_TYPE_COLORS } from '../types/graph';

const SERVICE_TYPE_OPTIONS = [
  { value: '', label: 'All Services' },
  { value: 's3', label: 'S3' },
  { value: 'lambda', label: 'Lambda' },
  { value: 'dynamodb', label: 'DynamoDB' },
];

function getServiceTypeColor(type: string): string {
  return SERVICE_TYPE_COLORS[type] || '#666666';
}

function formatServiceType(type: string): string {
  if (type.startsWith('s3:')) return 'S3';
  if (type.startsWith('lambda:')) return 'Lambda';
  if (type.startsWith('dynamodb:')) return 'DynamoDB';
  return type;
}

// Force-directed layout simulation (simple spring layout)
function calculateLayout(graphNodes: GraphNode[]): Node[] {
  const nodeCount = graphNodes.length;

  if (nodeCount === 0) return [];

  // Simple circular layout for better initial distribution
  const radius = Math.max(300, nodeCount * 20);
  const angleStep = (2 * Math.PI) / Math.max(nodeCount, 1);

  return graphNodes.map((node, index) => {
    const angle = index * angleStep;
    const x = radius * Math.cos(angle);
    const y = radius * Math.sin(angle);

    return {
      id: node.id,
      type: 'default',
      position: { x, y },
      data: {
        label: node.name,
        resource: node,
      },
      style: {
        background: getServiceTypeColor(node.type),
        color: '#fff',
        border: '2px solid #fff',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '12px',
        fontWeight: 'bold',
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });
}

function GraphContent() {
  const reactFlowInstance = useReactFlow();
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const [serviceType, setServiceType] = useState('');
  const [project, setProject] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const filters: GraphFilters = useMemo(() => ({
    tenant_id: tenantId || undefined,
    service_type: serviceType || undefined,
    project: project || undefined,
  }), [tenantId, serviceType, project]);

  const { data: graphData, isLoading, error } = useResourceGraph({ filters });

  const initialNodes = useMemo(() => {
    if (!graphData) return [];
    return calculateLayout(graphData.nodes);
  }, [graphData]);

  const initialEdges = useMemo((): Edge[] => {
    if (!graphData) return [];
    return graphData.edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: true,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
        color: '#999',
      },
      style: {
        strokeWidth: 2,
        stroke: '#999',
      },
    }));
  }, [graphData]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes and edges when data changes
  useMemo(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const resource = node.data.resource as GraphNode;
    setSelectedNode(resource);

    // Highlight connected nodes
    const connectedNodeIds = new Set<string>();
    connectedNodeIds.add(node.id);

    edges.forEach(edge => {
      if (edge.source === node.id) connectedNodeIds.add(edge.target);
      if (edge.target === node.id) connectedNodeIds.add(edge.source);
    });

    setNodes(nodes.map(n => ({
      ...n,
      style: {
        ...n.style,
        opacity: connectedNodeIds.has(n.id) ? 1 : 0.3,
      },
    })));

    setEdges(edges.map(e => ({
      ...e,
      style: {
        ...e.style,
        opacity: (e.source === node.id || e.target === node.id) ? 1 : 0.2,
      },
    })));
  }, [nodes, edges, setNodes, setEdges]);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    // Reset all opacities
    setNodes(nodes.map(n => ({
      ...n,
      style: {
        ...n.style,
        opacity: 1,
      },
    })));
    setEdges(edges.map(e => ({
      ...e,
      style: {
        ...e.style,
        opacity: 1,
      },
    })));
  }, [nodes, edges, setNodes, setEdges]);

  const handleExportPNG = useCallback(() => {
    const nodes = reactFlowInstance.getNodes();

    // Create a temporary canvas
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    if (!ctx) return;

    // Calculate bounds
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodes.forEach(node => {
      minX = Math.min(minX, node.position.x);
      minY = Math.min(minY, node.position.y);
      maxX = Math.max(maxX, node.position.x + 150);
      maxY = Math.max(maxY, node.position.y + 50);
    });

    const width = maxX - minX + 100;
    const height = maxY - minY + 100;

    canvas.width = width;
    canvas.height = height;

    // White background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    // Simple text-based export (for full export, use html2canvas or similar)
    ctx.fillStyle = '#000000';
    ctx.font = '14px sans-serif';
    ctx.fillText(`Resource Graph - ${graphData?.metadata.node_count || 0} nodes`, 20, 30);

    // Download
    canvas.toBlob(blob => {
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resource-graph-${Date.now()}.png`;
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  }, [reactFlowInstance, graphData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading resource graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-red-600">Error loading graph: {error instanceof Error ? error.message : 'Unknown error'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Resource Graph</h1>
            <p className="text-sm text-gray-600 mt-1">
              {graphData?.metadata.node_count || 0} nodes, {graphData?.metadata.edge_count || 0} edges
            </p>
          </div>

          {/* Filters */}
          <div className="flex items-center space-x-4">
            <div>
              <label htmlFor="service-type" className="sr-only">Service Type</label>
              <select
                id="service-type"
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                {SERVICE_TYPE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="project" className="sr-only">Project</label>
              <input
                id="project"
                type="text"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                placeholder="Filter by project..."
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <button
              onClick={handleExportPNG}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              Export PNG
            </button>
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          fitView
          minZoom={0.1}
          maxZoom={2}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const resource = node.data?.resource as GraphNode;
              return resource ? getServiceTypeColor(resource.type) : '#666';
            }}
          />
          <Panel position="top-left" className="bg-white p-4 rounded-lg shadow-lg">
            <div className="space-y-2 text-sm">
              <div className="font-semibold text-gray-900">Legend</div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 rounded" style={{ background: SERVICE_TYPE_COLORS['s3:bucket'] }}></div>
                <span className="text-gray-700">S3 Bucket</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 rounded" style={{ background: SERVICE_TYPE_COLORS['lambda:function'] }}></div>
                <span className="text-gray-700">Lambda Function</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 rounded" style={{ background: SERVICE_TYPE_COLORS['dynamodb:table'] }}></div>
                <span className="text-gray-700">DynamoDB Table</span>
              </div>
            </div>
          </Panel>
        </ReactFlow>

        {/* Selected Node Sidebar */}
        {selectedNode && (
          <div className="absolute top-4 right-4 w-80 bg-white rounded-lg shadow-xl border border-gray-200 p-6">
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Resource Details</h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">Name</label>
                <p className="mt-1 text-sm text-gray-900 font-medium">{selectedNode.name}</p>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">Type</label>
                <p className="mt-1">
                  <span
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium text-white"
                    style={{ background: getServiceTypeColor(selectedNode.type) }}
                  >
                    {formatServiceType(selectedNode.type)}
                  </span>
                </p>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">ID</label>
                <p className="mt-1 text-sm text-gray-900 font-mono break-all">{selectedNode.id}</p>
              </div>

              {selectedNode.project && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Project</label>
                  <p className="mt-1 text-sm text-gray-900">{selectedNode.project}</p>
                </div>
              )}

              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">Tenant ID</label>
                <p className="mt-1 text-sm text-gray-900 font-mono">{selectedNode.tenant_id}</p>
              </div>

              {selectedNode.created_at && (
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Created</label>
                  <p className="mt-1 text-sm text-gray-900">
                    {new Date(selectedNode.created_at).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ResourceGraph() {
  return (
    <ReactFlowProvider>
      <GraphContent />
    </ReactFlowProvider>
  );
}
