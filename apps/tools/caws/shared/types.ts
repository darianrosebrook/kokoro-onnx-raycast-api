/**
 * CAWS Shared Types and Interfaces
 *
 * Consolidated type definitions used across all CAWS tools
 *
 * @author @darianrosebrook
 */

// =============================================================================
// CORE INTERFACES
// =============================================================================

export interface ValidationDetailsSchema {
  type: 'object';
  properties: {
    passed: { type: 'boolean' };
    score: { type: 'number' };
    details: { type: 'object' };
  };
  required: ['passed', 'score', 'details'];
}

export interface ValidationResult {
  passed: boolean;
  score: number;
  details: any;
  errors?: string[];
  warnings?: string[];
  recommendations?: string[];
}

export interface GateResult extends ValidationResult {
  tier?: number | string;
  tierPolicy?: TierPolicy;
}

export interface AccessibilityResult {
  passed: boolean;
  score: number;
  details: any;
  violations: Array<{
    rule: string;
    severity: 'error' | 'warning' | 'info';
    message: string;
    location?: string;
  }>;
  recommendations: string[];
}

export interface PerformanceResult {
  endpoint: string;
  p95_ms: number;
  budget_ms: number;
  passed: boolean;
  deviation_percent: number;
  score: number;
  details: any;
}

export interface ContractDetails {
  endpoint: string;
  method: string;
  status: 'valid' | 'invalid' | 'warning';
  schema?: Record<string, any>;
  examples?: Array<{
    request?: Record<string, any>;
    response?: Record<string, any>;
  }>;
}

export interface NonFunctionalRequirements {
  performance?: {
    maxResponseTime?: number;
    throughput?: number;
  };
  security?: {
    authentication?: boolean;
    authorization?: boolean;
    encryption?: boolean;
  };
  reliability?: {
    availability?: number;
    errorRate?: number;
  };
}

export interface ContractValidationResult {
  passed: boolean;
  score: number;
  details: Record<string, any>;
  risk_tier?: number;
  acceptance?: string[];
  contracts?: ContractDetails[];
  non_functional?: NonFunctionalRequirements;
  errors: Array<{
    type: 'request' | 'response' | 'schema';
    endpoint: string;
    message: string;
    details?: any;
  }>;
  coverage: {
    endpointsTested: number;
    totalEndpoints: number;
    schemasValidated: number;
  };
}

export interface TrustScoreComponents {
  coverage_branch: number;
  mutation_score: number;
  contracts_consumer: boolean;
  contracts_provider: boolean;
  a11y_passed: boolean;
  perf_within_budget: boolean;
  flake_rate: number;
}

export interface TrustScoreResult {
  total_score: number;
  tier: string;
  components: TrustScoreComponents;
  breakdown: {
    coverage: number;
    mutation: number;
    contracts: number;
    a11y: number;
    perf: number;
    flake: number;
  };
  recommendations: string[];
}

// =============================================================================
// FEATURE FLAG TYPES
// =============================================================================

export interface FeatureFlag {
  name: string;
  description: string;
  enabled: boolean;
  rolloutPercentage: number;
  environment: string[];
  userGroups: string[];
  dependencies: string[];
  createdAt: string;
  updatedAt: string;
  killSwitch?: boolean;
}

export interface FeatureFlagUpdate {
  name: string;
  enabled?: boolean;
  rolloutPercentage?: number;
  environment?: string[];
  userGroups?: string[];
  killSwitch?: boolean;
}

export interface FeatureFlagEvaluation {
  enabled: boolean;
  flag: FeatureFlag;
  reason: string;
}

export interface FeatureContext {
  environment: string;
  userId?: string;
  userGroups?: string[];
  requestId?: string;
  metadata?: any;
}

// =============================================================================
// CONFIGURATION TYPES
// =============================================================================

export interface PerformanceBudget {
  api_p95_ms: number;
  ingestion_rate?: number;
  ocr_processing_ms?: number;
  speech_processing_per_second?: number;
}

export interface TierPolicy {
  min_branch: number;
  min_coverage: number;
  min_mutation: number;
  requires_contracts: boolean;
  requires_manual_review?: boolean;
}

// =============================================================================
// WAIVER AND OVERRIDE TYPES
// =============================================================================

export interface WaiverConfig {
  gate: string;
  reason: string;
  owner: string;
  expiry: string;
  compensating_control?: string;
  ticket_url?: string;
  approved_by?: string;
  created_at: string;
  status: 'active' | 'expired' | 'revoked';
}

export interface HumanOverride {
  approved_by: string;
  reason: string;
  waived_requirements: string[];
  expiry_date?: string;
}

export interface AIAssessment {
  confidence_level: number;
  uncertainty_areas: string[];
  recommended_pairing?: boolean;
}

export interface ExperimentConfig {
  enabled: boolean;
  timeboxed_hours?: number;
  success_criteria?: string[];
  expiry_date?: string;
}

// =============================================================================
// CAWS GATE TYPES
// =============================================================================

export interface CoverageData {
  branches: { pct: number };
  functions: { pct: number };
  lines: { pct: number };
  statements: { pct: number };
}

export interface MutationData {
  metrics: {
    killed?: number;
    survived?: number;
    totalDetected?: number;
  };
}

export interface ContractTestResults {
  numPassed: number;
  numTotal: number;
  consumer?: boolean;
  provider?: boolean;
}

export interface TierPolicyConfig {
  [tier: number]: TierPolicy;
}

export interface GateCheckOptions {
  tier: number;
  workingDirectory?: string;
  verbose?: boolean;
}

export interface GateConfig {
  enabled: boolean;
  threshold?: number;
  timeout?: number;
  retries?: number;
  options?: Record<string, any>;
  thresholds?: Record<string, number>;
  required?: boolean;
}

export interface ToolConfig {
  name?: string;
  version?: string;
  enabled?: boolean;
  config?: Record<string, any>;
  dependencies?: string[];
  command?: string;
  args?: string[];
}

export interface LoggingConfig {
  level: 'debug' | 'info' | 'warn' | 'error';
  format?: 'json' | 'text';
  output?: 'console' | 'file' | 'both';
  filePath?: string;
  file?: string;
  maxSize?: number;
  maxFiles?: number;
}

export interface FeatureConfig {
  name?: string;
  enabled: boolean;
  config?: Record<string, any>;
  dependencies?: string[];
}

export interface CawsConfig {
  version?: string;
  environment?: string;
  tiers: TierPolicyConfig;
  defaultTier: string;
  workingSpecPath: string;
  provenancePath: string;
  cawsDirectory: string;
  waiversPath?: string;
  paths?: Record<string, string>;
  gates?: Record<string, GateConfig>;
  tools?: Record<string, ToolConfig>;
  logging?: LoggingConfig;
  features?: Record<string, FeatureConfig | boolean>;
  waivers?: Record<string, WaiverConfig>;
  experiment_defaults?: ExperimentConfig;
}

// =============================================================================
// MIGRATION TYPES
// =============================================================================

export interface MigrationStep {
  id: string;
  description: string;
  sql: string;
  rollback_sql?: string;
  dependencies?: string[];
}

// =============================================================================
// TEST TYPES
// =============================================================================

export interface TestResult {
  title: string;
  fullName: string;
  status: 'passed' | 'failed' | 'pending' | 'skipped';
  duration: number;
  failureMessages: string[];
}

export interface TestSuiteResult {
  name: string;
  status: 'passed' | 'failed';
  testResults: TestResult[];
  startTime: number;
  endTime: number;
}

export interface FlakeDetectionResult {
  flakyTests: string[];
  varianceScore: number;
  totalRuns: number;
  recommendations: string[];
}

export interface HistoricalTestData {
  runs: TestRun[];
  quarantined: Set<string>;
  lastUpdated: string;
}

export interface TestRun {
  timestamp: number;
  results: Map<string, TestResult>;
  variance: number;
}

// =============================================================================
// PROVENANCE TYPES
// =============================================================================

export interface PerformanceMetrics {
  p95_ms?: number;
  p99_ms?: number;
  average_ms?: number;
  throughput?: number;
  error_rate?: number;
  budget_ms?: number;
  deviation_percent?: number;
}

export interface ProvenanceMetadata {
  environment?: string;
  branch?: string;
  pullRequest?: number;
  buildId?: string;
  deploymentId?: string;
  tags?: string[];
  custom?: Record<string, any>;
}

export interface ProvenanceData {
  agent: string;
  model: string;
  commit: string;
  artifacts: string[];
  results: {
    coverage_branch: number;
    mutation_score: number;
    tests_passed: number;
    a11y?: string;
    perf?: PerformanceMetrics;
    contracts?: {
      consumer: boolean;
      provider: boolean;
    };
    flake_rate?: number;
  };
  approvals: Array<{
    approver: string;
    timestamp: string;
    type: string;
  }>;
  generatedAt: string;
  metadata?: ProvenanceMetadata;
}

// =============================================================================
// MULTI-MODAL TYPES
// =============================================================================

export interface MultiModalIngestionConfig {
  batchSize?: number;
  rateLimitMs?: number;
  skipExisting?: boolean;
  includePatterns?: string[];
  excludePatterns?: string[];
  enableOCR?: boolean;
  enableSpeechToText?: boolean;
  maxFileSize?: number;
}

export interface MultiModalIngestionResult {
  totalFiles: number;
  processedFiles: number;
  skippedFiles: number;
  failedFiles: number;
  totalChunks: number;
  processedChunks: number;
  errors: string[];
  contentTypeStats: Record<string, number>;
}
