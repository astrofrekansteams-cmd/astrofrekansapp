"""Read-only review reproduction: isolated SQLite and fake payment providers.

Run from backend with tests on sys.path and conftest loaded as a pytest plugin.
These tests assert the observed defect, not the desired corrected behavior.
"""
import pytest

from test_payments import market, stores, wide_open, order_for, pay_externally


@pytest.mark.parametrize("actor", ["user", "expert"])
async def test_appointment_cancel_leaves_paid_order_without_refund(client, market, stores, actor):
    order_id = await order_for(client, market)
    _, paid, _ = await pay_externally(client, market, stores, order_id)
    assert paid.status_code == 200
    before_response = await client.get(f"/api/v1/orders/{order_id}", headers=market["user"]["headers"])
    assert before_response.status_code == 200
    before = before_response.json()
    assert before["payment_status"] == "paid"
    appointment_id = before["appointment"]["id"]
    prefix = "/expert" if actor == "expert" else ""
    cancelled = await client.post(
        f"/api/v1{prefix}/appointments/{appointment_id}/cancel",
        headers=market[actor]["headers"], json={"reason": "Review reproduction"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    after_response = await client.get(f"/api/v1/orders/{order_id}", headers=market["user"]["headers"])
    after = after_response.json()
    refunds = await client.get(f"/api/v1/orders/{order_id}/refund-requests", headers=market["user"]["headers"])
    assert refunds.status_code == 200
    assert after["status"] == before["status"]
    assert after["payment_status"] == "paid"
    assert refunds.json() == []
    print(f"REPRO actor={actor}; appointment=cancelled; order={after['status']}; payment=paid; refund_requests=0")
