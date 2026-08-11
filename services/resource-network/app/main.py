from fastapi import FastAPI

app = FastAPI(title="resource-network", version="0.1.0", description="Resource Matching Engine, Inventory (rig/equipment/labour), Document/Media Storage")


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
