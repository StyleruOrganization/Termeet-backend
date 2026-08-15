from typing import Literal, Union
from pydantic import BaseModel, Field


class ClientErrorTelemetry(BaseModel):
    type: Literal[
        "client_error", "unhandled_rejection", "react_error_boundary"
    ] = "client_error"
    message: str = ""
    stack: str | None = None
    componentStack: str | None = None
    href: str | None = None
    pathname: str | None = None
    viewport: str | None = None
    userAgent: str | None = None
    userId: str | None = None
    ts: int | None = None


class WebVitalTelemetry(BaseModel):
    type: Literal["web_vital"] = "web_vital"
    name: Literal["LCP", "FCP", "CLS", "INP", "TTFB"]
    value: float
    rating: Literal["good", "needs-improvement", "poor", "unknown"] = "unknown"
    delta: float | None = None
    id: str | None = None
    href: str | None = None
    ts: int | None = None


TelemetryPayload = Union[WebVitalTelemetry, ClientErrorTelemetry]
