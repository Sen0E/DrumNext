from fastapi import APIRouter, Request

from drumnext.domain.content import Layout, Score, ScoreSummary
from drumnext.transport.events import EventHub

router = APIRouter(tags=["content"])


@router.get("/scores", response_model=list[ScoreSummary])
async def list_scores(request: Request) -> list[ScoreSummary]:
    return request.app.state.scores.list()


@router.get("/scores/{score_id}", response_model=Score)
async def get_score(score_id: str, request: Request) -> Score:
    return request.app.state.scores.get(score_id)


@router.get("/layout", response_model=Layout)
async def get_layout(request: Request) -> Layout:
    return request.app.state.layout.get()


@router.put("/layout", response_model=Layout)
async def update_layout(layout: Layout, request: Request) -> Layout:
    async with request.app.state.command_lock:
        updated = request.app.state.layout.update(layout)
        await _broadcast_layout_changed(request, updated)
        return updated


@router.post("/layout/reset", response_model=Layout)
async def reset_layout(request: Request) -> Layout:
    async with request.app.state.command_lock:
        default = request.app.state.layout.reset()
        await _broadcast_layout_changed(request, default)
        return default


async def _broadcast_layout_changed(request: Request, layout: Layout) -> None:
    events: EventHub = request.app.state.events
    message = await events.envelope(
        "layout.changed", layout.model_dump(by_alias=True, mode="json")
    )
    await events.broadcast(message)
