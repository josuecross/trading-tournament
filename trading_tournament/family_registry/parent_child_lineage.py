"""Parent/child lineage contract for future strategy follow-ups."""

REQUIRED_LINEAGE_FIELDS = [
    "parent_candidate_id",
    "parent_status",
    "parent_failure_reason",
    "exact_parent_remains_closed",
    "one_major_changed_dimension",
    "unchanged_dimensions",
    "why_this_is_not_a_rescue",
    "valid_future_outcomes",
]

DISCOVERY_BLOCKED_IF_PARENT_RULE_MISMATCH = True
