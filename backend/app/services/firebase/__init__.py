"""Firebase: identity, Firestore chat, RTDB presence, Storage and FCM.

Nothing outside this package imports `firebase_admin`. See
docs/firebase_backend.md for the source-of-truth boundary: authorisation lives
in Postgres, realtime transport lives in Firebase, and Firestore rules are
defence in depth rather than the business rules themselves.
"""
