"""Background workers.

Separate processes, not FastAPI `BackgroundTasks`: a premium report can take
tens of seconds, and work tied to a request process dies with a deploy, a
restart or a crashed request. A worker is scaled, restarted and watched on its
own.
"""
