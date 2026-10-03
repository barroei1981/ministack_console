export interface LambdaFunction {
  name: string;
  tenant_id: string;
  project: string | null;
  arn: string;
  created_at: string;
  runtime: string;
  handler: string;
  memory: number;
  timeout: number;
  environment: Record<string, string>;
  last_modified: string;
  code_size: number;
  tags: Record<string, string>;
  state: Record<string, unknown>;
}

export interface CreateFunctionRequest {
  name: string;
  runtime: string;
  handler: string;
  code: string; // Base64-encoded ZIP
  tenant_id: string;
  project?: string;
  environment?: Record<string, string>;
  memory?: number;
  timeout?: number;
  tags?: Record<string, string>;
}

export interface FunctionListResponse {
  functions: LambdaFunction[];
  tenant_id: string;
  total: number;
}

export interface DeleteFunctionResponse {
  deleted: string;
}

export const LAMBDA_RUNTIMES = [
  { value: 'python3.11', label: 'Python 3.11' },
  { value: 'python3.10', label: 'Python 3.10' },
  { value: 'python3.9', label: 'Python 3.9' },
  { value: 'nodejs18.x', label: 'Node.js 18.x' },
  { value: 'nodejs16.x', label: 'Node.js 16.x' },
  { value: 'java17', label: 'Java 17' },
  { value: 'java11', label: 'Java 11' },
  { value: 'dotnet6', label: '.NET 6' },
  { value: 'go1.x', label: 'Go 1.x' },
  { value: 'ruby3.2', label: 'Ruby 3.2' },
] as const;
