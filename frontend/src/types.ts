export type DocType = 'sop' | 'policy' | 'previous'

export type DocStatus =
  | 'pending'
  | 'needs_password'
  | 'needs_ocr'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'ready'
  | 'failed'

export interface Document {
  id: string
  name: string
  doc_type: DocType
  status: DocStatus
  path: string
  is_locked: boolean
  pages: number | null
  extraction_mode: string | null
  chunk_count: number | null
  error: string | null
  created_at: string
  updated_at: string
}

export type TestLevel = 'pentest' | 'dast' | 'none'

export interface Scope {
  in_scope: string[]
  out_of_scope: string[]
  test_methods: string[]
  environments: string[]
  effort_estimate: string
}

export interface Decision {
  requires_pentest: boolean
  test_level: TestLevel
  classification_reason: string
  risk_factors: string[]
  scope: Scope
}

export interface FiredRule {
  id: string
  name: string
  test_level: TestLevel
  priority: string
  reasoning: string
  cap?: TestLevel | null
}

export interface FormField {
  label: string
  options: string[]
  selected: string[]
  source_line: string
  page: number
}

export interface Conflict {
  field: string
  rules_value: unknown
  llm_value: unknown
  explanation: string
}

export type ReviewStatus = 'running' | 'completed' | 'failed'

export interface Review {
  id: string
  status: ReviewStatus
  frd_name: string
  nfrd_name: string
  facts: Record<string, unknown> | null
  rule_engine_enabled: boolean
  detected_exposure: string | null
  exposure_override: string | null
  form_fields: FormField[]
  retrieved_sources: string[]
  rules_fired: FiredRule[]
  rule_test_level: TestLevel | null
  llm_decision: Decision | null
  conflicts: Conflict[]
  final_decision: Decision | null
  error: string | null
  created_at: string
  updated_at: string
  frd_text?: string
  nfrd_text?: string
}

export interface Health {
  status: string
  ollama: boolean
  models: string[]
  reasoning_model: string
  embedding_model: string
  enable_rule_engine: boolean
  documents_indexed: number
}

export interface ModelsInfo {
  available: string[]
  reasoning_model: string
  embedding_model: string
}
