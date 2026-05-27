EVALUATIONS = {

    "Login API": {
        "technical_correctness": "yes",
        "automation_ready": "partial",
        "assertions_testable": "partial",
        "oracle_correct": "yes",
        "edge_case_realism": "good",
        "summary": "Most models correctly model JWT auth...",
        "strengths": [
            "Concrete endpoint (/api/login) and HTTP status assertions in compound and compound-mini outputs",
            "Correct 200/401 pass/fail oracle consistently across all passing runs"
        ],
        "weaknesses": [
            "No JWT structure validation",
            "No token refresh or blacklist coverage"
        ],
        "critical_failures": [],
        "suggested_tags": [
            "jwt-validation",
            "api-automation",
            "missing-field-edge"
        ]
    },

    "Payment API": {
        "technical_correctness": "partial",
        "automation_ready": "no",
        "assertions_testable": "partial",
        "oracle_correct": "partial",
        "edge_case_realism": "partial",
        "summary": "All successful outputs are structurally identical...",
        "strengths": [
            "Timeout handling is scenario-relevant"
        ],
        "weaknesses": [
            "No endpoint or payload definitions"
        ],
        "critical_failures": [
            "No model specifies payment API schema"
        ],
        "suggested_tags": [
            "missing-payloads",
            "ambiguous-oracle"
        ]
    },

    "SQL Injection": {
        "technical_correctness": "partial",
        "automation_ready": "partial",
        "assertions_testable": "partial",
        "oracle_correct": "no",
        "edge_case_realism": "good",
        "summary": "Critical oracle inversion detected.",
        "strengths": [
            "Realistic SQLi payloads"
        ],
        "weaknesses": [
            "No blind SQLi coverage"
        ],
        "critical_failures": [
            "PASS condition equals successful exploit"
        ],
        "suggested_tags": [
            "inverted-oracle",
            "security-oracle-failure"
        ]
    },

    "Session Hijacking": {
        "technical_correctness": "partial",
        "automation_ready": "partial",
        "assertions_testable": "partial",
        "oracle_correct": "yes",
        "edge_case_realism": "partial",
        "summary": "Scenario mismatch: models test expiry instead of hijacking.",
        "strengths": [
            "Correct expired-token assertions"
        ],
        "weaknesses": [
            "No replay or fixation testing"
        ],
        "critical_failures": [
            "Scenario name universally ignored"
        ],
        "suggested_tags": [
            "scenario-mismatch",
            "token-expiry-only"
        ]
    },

    "Ambiguous Booking": {
        "technical_correctness": "partial",
        "automation_ready": "no",
        "assertions_testable": "partial",
        "oracle_correct": "yes",
        "edge_case_realism": "poor",
        "summary": "Core ambiguity challenge completely missed.",
        "strengths": [
            "Booking confirmation assertions are concrete"
        ],
        "weaknesses": [
            "No clarification handling"
        ],
        "critical_failures": [
            "Scenario comprehension failure"
        ],
        "suggested_tags": [
            "ambiguity-handling-missing",
            "scenario-comprehension-failure"
        ]
    }

}