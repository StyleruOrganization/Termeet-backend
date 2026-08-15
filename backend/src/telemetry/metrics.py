from prometheus_client import Counter, Histogram

# Frontend Web Vitals
FRONTEND_WEB_VITAL_SECONDS = Histogram(
    "frontend_web_vital_duration_seconds",
    "Frontend Web Vital metric durations in seconds (LCP, FCP, INP, TTFB)",
    ["metric", "rating"],
    buckets=[0.05, 0.1, 0.25, 0.5, 0.8, 1.2, 1.8, 2.5, 4.0, 6.0, 10.0],
)

FRONTEND_CLS_SCORE = Histogram(
    "frontend_cumulative_layout_shift_score",
    "Frontend Cumulative Layout Shift score",
    ["rating"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1.0],
)

FRONTEND_CLIENT_ERRORS_TOTAL = Counter(
    "frontend_client_errors_total",
    "Total count of frontend runtime JS errors reported by clients",
    ["type"],
)

# Business metrics
MEETINGS_CREATED_TOTAL = Counter(
    "termeet_meetings_created_total",
    "Total number of meetings created",
    ["source"],
)

SLOTS_SAVED_TOTAL = Counter(
    "termeet_slots_saved_total",
    "Total number of slot save operations on meetings",
    ["auth_status"],
)

USERS_REGISTERED_TOTAL = Counter(
    "termeet_users_registered_total",
    "Total number of new users registered",
    ["provider"],
)
