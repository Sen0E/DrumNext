from fastapi import APIRouter, Request

from drumnext.domain.content import EndingAnimationSettings, ProjectionVisualSettings
from drumnext.transport.events import EventHub

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ending-animation", response_model=EndingAnimationSettings)
async def get_ending_animation(request: Request) -> EndingAnimationSettings:
    return request.app.state.ending_animation.get()


@router.put("/ending-animation", response_model=EndingAnimationSettings)
async def update_ending_animation(
    settings: EndingAnimationSettings, request: Request
) -> EndingAnimationSettings:
    async with request.app.state.command_lock:
        updated = request.app.state.ending_animation.update(settings)
        events: EventHub = request.app.state.events
        message = await events.envelope(
            "ending_animation.changed", updated.model_dump(mode="json")
        )
        await events.broadcast(message)
        return updated


@router.get("/projection-visuals", response_model=ProjectionVisualSettings)
async def get_projection_visuals(request: Request) -> ProjectionVisualSettings:
    return request.app.state.projection_visuals.get()


@router.put("/projection-visuals", response_model=ProjectionVisualSettings)
async def update_projection_visuals(
    settings: ProjectionVisualSettings, request: Request
) -> ProjectionVisualSettings:
    async with request.app.state.command_lock:
        updated = request.app.state.projection_visuals.update(settings)
        events: EventHub = request.app.state.events
        message = await events.envelope(
            "projection_visuals.changed",
            updated.model_dump(by_alias=True, mode="json"),
        )
        await events.broadcast(message)
        return updated
