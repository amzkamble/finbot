/* TypeScript interfaces matching backend Pydantic models */

export interface User {
  id: string;
  username: string;
  role: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface SourceInfo {
  document: string;
  page: number;
  section: string;
  collection: string;
  chunk_type: string;
}

export interface RouteInfo {
  name: string;
  confidence: number;
  was_rbac_filtered: boolean;
  original_route?: string;
  collections_searched: string[];
}

export interface InputGuardInfo {
  pii_scrubbed: boolean;
  off_topic_score: number;
  injection_detected: boolean;
  rate_limit_remaining?: number;
}

export interface OutputGuardInfo {
  grounding_score: number;
  grounding_warning: boolean;
  leakage_detected: boolean;
  citations_valid: boolean;
  citations_auto_added: boolean;
}

export interface GuardrailInfo {
  input: InputGuardInfo;
  output: OutputGuardInfo;
}

export interface ChatResponse {
  answer: string;
  sources: SourceInfo[];
  route: RouteInfo;
  guardrails: GuardrailInfo;
  blocked: boolean;
  blocked_reason?: string;
  metadata: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: SourceInfo[];
  route?: RouteInfo;
  guardrails?: GuardrailInfo;
  blocked?: boolean;
  blocked_reason?: string;
  metadata?: Record<string, any>;
}

export interface DocumentInfo {
  filename: string;
  collection: string;
  chunk_count: number;
  access_roles: string[];
}

export interface StatsResponse {
  total_documents: number;
  total_chunks: number;
  chunks_by_collection: Record<string, number>;
  chunks_by_type: Record<string, number>;
  total_users: number;
  users_by_role: Record<string, number>;
}

/* Demo users for login page cards */
export const DEMO_USERS = [
  { username: 'john_employee', password: 'demo123', role: 'employee', label: 'General Employee', icon: '👤', description: 'Access to general company documents only' },
  { username: 'sarah_finance', password: 'demo123', role: 'finance_analyst', label: 'Finance Analyst', icon: '💰', description: 'Access to general + finance documents' },
  { username: 'mike_engineer', password: 'demo123', role: 'engineer', label: 'Engineer', icon: '⚙️', description: 'Access to general + engineering documents' },
  { username: 'lisa_marketing', password: 'demo123', role: 'marketing_specialist', label: 'Marketing Specialist', icon: '📊', description: 'Access to general + marketing documents' },
  { username: 'alex_executive', password: 'demo123', role: 'executive', label: 'Executive', icon: '👔', description: 'Full access to all departments' },
  { username: 'emma_hr', password: 'demo123', role: 'hr_representative', label: 'HR Representative', icon: '🤝', description: 'Access to general + HR documents' },
];

/* Collection color mapping */
export const COLLECTION_COLORS: Record<string, string> = {
  finance: '#10b981',
  engineering: '#3b82f6',
  marketing: '#f59e0b',
  hr: '#8b5cf6',
  general: '#6b7280',
};
