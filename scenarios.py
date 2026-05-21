SCENARIOS = [

    {
        "name": "Authentication",
        "feature": (
            "User login with email and password. "
            "The system validates credentials, "
            "locks the account after 5 failed attempts, "
            "supports remember-me for 30 days, "
            "and sends a verification email "
            "on first login from a new device."
        )
    },

    {
        "name": "Ecommerce Checkout",
        "feature": (
            "Users can add products to cart, "
            "apply coupons, retry failed payments, "
            "and cancel orders before dispatch."
        )
    },

    {
        "name": "Bank Transfer",
        "feature": (
            "Users can transfer money between accounts "
            "with OTP verification, daily transfer limits, "
            "and fraud detection for suspicious activity."
        )
    },

    {
        "name": "File Upload",
        "feature": (
            "Users can upload profile pictures with "
            "file type validation, size limits, "
            "virus scanning, and duplicate detection."
        )
    },

    {
        "name": "REST API",
        "feature": (
            "REST API with JWT authentication, "
            "rate limiting, pagination, "
            "and role-based authorization."
        )
    },

    {
        "name": "Appointment Booking",
        "feature": (
            "Patients can book appointments with doctors "
            "based on availability, cancellation rules, "
            "and automated reminders."
        )
    },

]