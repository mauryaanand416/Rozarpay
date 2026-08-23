export type Action = "ALLOW" | "REVIEW" | "BLOCK" | "ESCALATE";

export interface Reason {
  source: string;
  code: string;
  description: string;
  min_action?: string;
  impact?: number | null;
}

export interface Transaction {
  txn_ref: string;
  event_time: string;
  amount: number;
  currency: string;
  customer_id: string;
  merchant_id: string;
  payment_method: string;
  device_id: string;
  ip_country: string;
  billing_country: string;
  channel: string;
}

export interface DecisionEvent {
  decision_id: number;
  txn_ref: string;
  risk_score: number | null;
  action: Action;
  reasons: Reason[];
  model_version: string;
  threshold_used: { t_review: number; t_block: number };
  latency_ms: number;
  created_at: string;
  explanation: string | null;
  explanation_source: string | null;
  transaction: Transaction;
}

export interface ModelMetrics {
  model_version?: string;
  pr_auc?: number;
  roc_auc?: number;
  brier?: number;
  fraud_rate?: number;
  dataset_rows?: number;
  split?: { train_rows: number; test_rows: number; strategy: string };
  review_threshold?: ThresholdMetrics;
  block_threshold?: ThresholdMetrics;
  cost_optimal_threshold?: {
    threshold: number;
    recall_at_threshold: number;
    value_recall: number;
  };
  feature_importance_gain?: Record<string, number>;
}

export interface ThresholdMetrics {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  f2: number;
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number };
}

export interface LiveStats {
  window_hours: number;
  total_transactions: number;
  by_action: Record<string, number>;
  avg_latency_ms: number;
  blocked_or_escalated_value_inr: number;
  review_queue_value_inr: number;
  top_rule_hits: Record<string, number>;
}

export interface AuditItem {
  seq: number;
  decision_id: number | null;
  actor: string;
  action_type: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
  created_at: string;
}
