export interface GraphNode {
  id: string;
  name: string;
  type: string;
  tenant_id: string;
  project?: string;
  created_at?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export interface GraphMetadata {
  node_count: number;
  edge_count: number;
  filters: {
    tenant_id?: string;
    project?: string;
    service_type?: string;
  };
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: GraphMetadata;
}

export interface GraphFilters {
  tenant_id?: string;
  project?: string;
  service_type?: string;
}

export const SERVICE_TYPE_COLORS: Record<string, string> = {
  's3:bucket': '#FF9900',      // AWS S3 orange
  'lambda:function': '#FF9900', // AWS Lambda orange
  'dynamodb:table': '#4053D6',  // AWS DynamoDB blue
  default: '#666666',
};
