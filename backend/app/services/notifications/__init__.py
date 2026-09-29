"""Push notifications: devices, the outbox, and delivery.

Push is never on the critical path of a business transaction - a request writes
an outbox row and returns, and a worker delivers it. See
docs/push_notifications.md.
"""
