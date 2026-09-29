"""Version 1 of the public API."""

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    billing,
    calls,
    chat,
    coins,
    divination,
    firebase_auth,
    marketplace,
    notifications,
    orders,
    astrology,
    auth,
    compatibility,
    forecasts,
    guides,
    health,
    horary,
    services,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(astrology.router)
api_router.include_router(forecasts.router)
api_router.include_router(guides.router)
api_router.include_router(horary.router)
api_router.include_router(compatibility.router)
api_router.include_router(ai.router)
api_router.include_router(divination.router)
api_router.include_router(marketplace.router)
api_router.include_router(orders.router)
api_router.include_router(orders.expert_router)
api_router.include_router(firebase_auth.router)
api_router.include_router(chat.router)
api_router.include_router(chat.device_router)
api_router.include_router(calls.router)
api_router.include_router(calls.webhook_router)
api_router.include_router(billing.router)
api_router.include_router(coins.router)
api_router.include_router(billing.order_router)
api_router.include_router(billing.expert_router)
api_router.include_router(billing.webhook_router)
api_router.include_router(services.router)
api_router.include_router(notifications.router)

# Probes live outside the versioned prefix as well; see app/main.py.
system_router = APIRouter()
system_router.include_router(health.router)
