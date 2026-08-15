import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Response, status
import aio_pika
from sqlalchemy import text

from backend.src.database import async_session_maker
from .metrics import (
    FRONTEND_CLIENT_ERRORS_TOTAL,
    FRONTEND_CLS_SCORE,
    FRONTEND_WEB_VITAL_SECONDS,
)
from .schemas import ClientErrorTelemetry, WebVitalTelemetry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telemetry & Health"])


@router.get(
    "/health",
    summary="Healthcheck сервиса",
    description="Проверяет доступность базы данных и брокера сообщений",
)
async def healthcheck(request: Request) -> Dict[str, Any]:
    health_status: Dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "rabbitmq": "disabled",
    }

    # 1. Проверка подключения к PostgreSQL
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        logger.error("Healthcheck DB error: %s", e)
        health_status["status"] = "error"
        health_status["database"] = "unhealthy"

    # 2. Проверка подключения к RabbitMQ (если инициализирован в приложении)
    rabbitmq = getattr(request.app.state, "rabbitmq", None)
    if rabbitmq is not None:
        try:
            channel = getattr(rabbitmq, "channel", None)
            if channel and not channel.is_closed:
                health_status["rabbitmq"] = "ok"
            else:
                health_status["rabbitmq"] = "disconnected"
        except Exception as e:
            logger.warning("Healthcheck RabbitMQ error: %s", e)
            health_status["rabbitmq"] = "unhealthy"

    if health_status["status"] != "ok" or health_status["database"] != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status,
        )

    return health_status


@router.post(
    "/telemetry",
    summary="Прием клиентской телеметрии (Web Vitals и JS-ошибки)",
    status_code=status.HTTP_200_OK,
)
async def receive_telemetry(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, str]:
    telemetry_type = payload.get("type", "client_error")

    if telemetry_type == "web_vital":
        try:
            vital = WebVitalTelemetry.model_validate(payload)
            rating = vital.rating or "unknown"
            if vital.name == "CLS":
                FRONTEND_CLS_SCORE.labels(rating=rating).observe(vital.value)
            else:
                # В Web Vitals значение миллисекунды -> переводим в секунды для Prometheus
                seconds_val = vital.value / 1000.0 if vital.value > 0 else 0.0
                FRONTEND_WEB_VITAL_SECONDS.labels(
                    metric=vital.name, rating=rating
                ).observe(seconds_val)
        except Exception as e:
            logger.debug("Failed to process web_vital telemetry: %s", e)
    else:
        try:
            err = ClientErrorTelemetry.model_validate(payload)
            err_type = err.type or "client_error"
            FRONTEND_CLIENT_ERRORS_TOTAL.labels(type=err_type).inc()
            logger.warning(
                "Frontend client error: %s (pathname=%s, viewport=%s, type=%s, userAgent=%s)",
                err.message[:200],
                err.pathname or err.href,
                err.viewport or "unknown",
                err_type,
                (err.userAgent or "")[:50],
            )

            # Мгновенная отправка детального алерта в Telegram через RabbitMQ без задержек
            rabbitmq = getattr(request.app.state, "rabbitmq", None)
            if rabbitmq:
                alert_payload = {
                    "source": "frontend_telemetry",
                    "type": err_type,
                    "message": err.message,
                    "stack": err.stack,
                    "componentStack": err.componentStack,
                    "pathname": err.pathname or err.href,
                    "viewport": err.viewport,
                    "userAgent": err.userAgent,
                    "userId": err.userId,
                }
                msg = aio_pika.Message(
                    body=json.dumps(alert_payload, ensure_ascii=False).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                )
                await rabbitmq.publish("alerts_queue", msg)
        except Exception as e:
            logger.debug("Failed to process client_error telemetry: %s", e)

    return {"status": "ok"}


@router.post(
    "/telemetry/alerts/webhook",
    summary="Webhook от Alertmanager для отправки в RabbitMQ alerts_queue",
    status_code=status.HTTP_200_OK,
)
async def alertmanager_webhook(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, str]:
    rabbitmq = getattr(request.app.state, "rabbitmq", None)
    if not rabbitmq:
        logger.warning("RabbitMQ is not connected, alert dropped")
        return {"status": "rabbitmq_not_connected"}

    try:
        message = aio_pika.Message(
            body=json.dumps(payload, ensure_ascii=False).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await rabbitmq.publish("alerts_queue", message)
        logger.info(
            "Alert forwarded to alerts_queue in RabbitMQ (status=%s, alerts=%d)",
            payload.get("status"),
            len(payload.get("alerts", [])),
        )
    except Exception as e:
        logger.error("Failed to forward alert to RabbitMQ: %s", e)
        return {"status": "error", "detail": str(e)}

    return {"status": "ok"}

