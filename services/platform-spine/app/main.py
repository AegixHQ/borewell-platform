from fastapi import FastAPI

app = FastAPI(title="platform-spine", version="0.1.0", description="Identity/RBAC, Job Orchestration state machine, Notifications, Gateway routing")


@app.get("/healthz")
def healthz():
    """Liveness check - does the process respond at all."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness check - are this service's dependencies reachable.
    TODO: add a real DB connectivity check once persistence is wired up.
    """
    return {"status": "ready"}
