"""The cube endpoint - one route that answers the query shapes fifty bespoke endpoints answer today.

Three things happen here and nowhere else in the request path:

1. **The registry validates before anything is built.** `reg.validate_scope` raises by name for an
   illegal metric x dimension, and that message - which already lists the supported dimensions for
   that metric - is passed through to the caller verbatim. A refused scope with a named alternative
   is the contract; a silently mis-joined grouping that renders a plausible wrong number is the
   failure this exists to prevent.

2. **The SQLite read runs in a threadpool.** `fact_store` is synchronous sqlite3, and FastAPI runs
   `async def` handlers on the event loop. A direct call would block every other request for the
   duration of the rollup.

3. **No EDW call.** `databricks_client` holds one process-lifetime connection behind one lock with a
   150-800s cold-start tax. A route that fell through to live SQL would serialize the whole app
   behind it, so this reads only what `refresh_service` has already materialized.

Status codes are chosen so a caller can act on them: 404 for a metric the registry has never heard
of (a typo or a stale client), 422 for a metric that exists but cannot answer this shape (a scope
problem the caller can fix by changing the group-by).
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.semantics import registry as reg
from app.services import cube_service

router = APIRouter(prefix="/api/mosaic", tags=["cube"])


class CubeRequest(BaseModel):
    """A scope. Every field is optional except `metrics`, and the defaults are the enterprise view.

    POST rather than GET because a scope is a structured object with two list fields, and encoding
    repeated `metric=`/`group_by=` params is where client and server quietly disagree about
    ordering. Nothing here mutates state.
    """

    metrics: list[str] = Field(..., min_length=1)
    group_by: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None
    period_from: str | None = None  # 'YYYY-MM-DD'; the day is ignored, months are the grain
    period_to: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20000)


@router.post("/cube")
async def query_cube(req: CubeRequest) -> dict:
    """Answer a scope from the cube, with each metric's governed definition attached.

    `validate_scope` runs first and on the *registry's* dimension vocabulary, which is deliberately
    narrower than what the cube physically stores - `radiologist` rows exist in `mosaic_fact` for
    Entity 360 but are not yet a group-by dimension, because rolling a rate up across the ~70
    managing practices one radiologist reads at has no governed definition yet. Reaching those rows
    is done by naming `entity_type`, not by grouping.
    """
    try:
        reg.validate_scope(req.metrics, req.group_by)
        result = await run_in_threadpool(
            cube_service.query,
            metrics=req.metrics,
            group_by=req.group_by,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            period_from=req.period_from,
            period_to=req.period_to,
            limit=req.limit,
        )
    except reg.UnknownMetricError as exc:
        # KeyError stringifies with its own quotes; str(exc) would render as "'no such metric...'".
        raise HTTPException(status_code=404, detail=exc.args[0] if exc.args else str(exc))
    except reg.UnsupportedDimensionError as exc:
        # 422, not 400: the request is well-formed, it just asks for something this metric cannot
        # answer. The message already names the supported alternatives - carry it through unedited.
        raise HTTPException(status_code=422, detail=str(exc))
    return result


@router.get("/cube/status")
async def cube_status() -> dict:
    """What the cube currently holds - row count, measures, entity types, period span.

    Exposed because "the number is missing" and "the cube has not been refreshed since the schema
    changed" look identical from the UI, and the frozen-`edw_test` incident proved that a surface
    with no freshness signal will serve stale numbers confidently.
    """
    return await run_in_threadpool(cube_service.status)
