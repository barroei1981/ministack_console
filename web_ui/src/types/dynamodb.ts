export interface KeySchemaElement {
  AttributeName: string;
  KeyType: 'HASH' | 'RANGE';
}

export interface AttributeDefinition {
  AttributeName: string;
  AttributeType: 'S' | 'N' | 'B'; // String, Number, Binary
}

export interface ProvisionedThroughput {
  ReadCapacityUnits: number;
  WriteCapacityUnits: number;
}

export interface DynamoDBTable {
  name: string;
  tenant_id: string;
  project?: string;
  arn: string;
  created_at: string;
  key_schema: KeySchemaElement[];
  attribute_definitions: AttributeDefinition[];
  billing_mode: 'PAY_PER_REQUEST' | 'PROVISIONED';
  table_status: string;
  item_count: number;
  tags: Record<string, string>;
  state: {
    key_schema: KeySchemaElement[];
    attribute_definitions: AttributeDefinition[];
    billing_mode: string;
    table_status: string;
    item_count: number;
  };
}

export interface CreateTableRequest {
  name: string;
  key_schema: KeySchemaElement[];
  attribute_definitions: AttributeDefinition[];
  billing_mode: 'PAY_PER_REQUEST' | 'PROVISIONED';
  provisioned_throughput?: ProvisionedThroughput;
  tenant_id: string;
  project?: string;
  tags?: Record<string, string>;
}

export interface TableListResponse {
  tables: DynamoDBTable[];
  tenant_id: string;
  total: number;
}

export interface DynamoDBItem {
  [key: string]: any;
}

export interface ScanItemsResponse {
  items: DynamoDBItem[];
  count: number;
  last_evaluated_key?: Record<string, any>;
}

export const ATTRIBUTE_TYPES = [
  { value: 'S', label: 'String' },
  { value: 'N', label: 'Number' },
  { value: 'B', label: 'Binary' },
] as const;

export const BILLING_MODES = [
  { value: 'PAY_PER_REQUEST', label: 'On-demand' },
  { value: 'PROVISIONED', label: 'Provisioned' },
] as const;
