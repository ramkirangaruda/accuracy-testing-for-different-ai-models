SCENARIOS = [

    # =========================
    # BANKING
    # =========================

    {
        "name": "Bank Login",
        "feature": (
            "User login with email and password. "
            "System locks account after 5 failed attempts. "
            "Remember-me works for 30 days."
        ),
        "type": "functional",
        "domain": "banking",
        "difficulty": "easy"
    },

    {
        "name": "Invalid IFSC Transfer",
        "feature": (
            "Money transfer with invalid IFSC code."
        ),
        "type": "edge_case",
        "domain": "banking",
        "difficulty": "medium"
    },

    # =========================
    # ECOMMERCE
    # =========================

    {
        "name": "Refund Request",
        "feature": (
            "Customer requests refund for delayed package."
        ),
        "type": "customer_support",
        "domain": "ecommerce",
        "difficulty": "easy"
    },

    {
        "name": "Angry Customer",
        "feature": (
            "Customer complains order has not arrived for 15 days."
        ),
        "type": "edge_case",
        "domain": "ecommerce",
        "difficulty": "medium"
    },

    # =========================
    # API TESTING
    # =========================

    {
        "name": "Login API",
        "feature": (
            "REST API login endpoint with JWT authentication."
        ),
        "type": "api",
        "domain": "backend",
        "difficulty": "medium"
    },

    {
        "name": "Payment API",
        "feature": (
            "Payment API with transaction verification and timeout handling."
        ),
        "type": "api",
        "domain": "backend",
        "difficulty": "hard"
    },

    # =========================
    # SECURITY
    # =========================

    {
        "name": "SQL Injection",
        "feature": (
            "Login form vulnerable to SQL injection attempts."
        ),
        "type": "security",
        "domain": "security",
        "difficulty": "hard"
    },

    {
        "name": "Session Hijacking",
        "feature": (
            "User session management and token expiration."
        ),
        "type": "security",
        "domain": "security",
        "difficulty": "hard"
    },

    # =========================
    # EDGE CASES
    # =========================

    {
        "name": "Ambiguous Booking",
        "feature": (
            "Book me a hotel tomorrow."
        ),
        "type": "edge_case",
        "domain": "general",
        "difficulty": "hard"
    },

    {
        "name": "Missing Information",
        "feature": (
            "Calculate EMI for my loan."
        ),
        "type": "edge_case",
        "domain": "general",
        "difficulty": "hard"
    }

]