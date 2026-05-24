"""GitLab webhook receiver — processes CI/CD events from GitLab pipelines."""
import json
from fastapi import APIRouter, Request, Header, HTTPException
from app.config import settings
from app.utils.logger import logger

router = APIRouter()


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(None),
    x_gitlab_event: str = Header(None),
):
    if settings.GITHUB_WEBHOOK_SECRET and x_gitlab_token:
        if x_gitlab_token != settings.GITHUB_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid token")

    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info(f"GitLab webhook received: event={x_gitlab_event}")

    if x_gitlab_event == "Pipeline Hook":
        await _handle_pipeline(payload)
    elif x_gitlab_event == "Push Hook":
        await _handle_push(payload)
    elif x_gitlab_event == "Merge Request Hook":
        await _handle_merge_request(payload)

    return {"received": True, "event": x_gitlab_event}


async def _handle_pipeline(payload: dict):
    attrs = payload.get("object_attributes", {})
    logger.debug(f"GitLab pipeline: id={attrs.get('id')}, status={attrs.get('status')}")


async def _handle_push(payload: dict):
    repo = payload.get("project", {}).get("path_with_namespace")
    logger.debug(f"GitLab push: repo={repo}")


async def _handle_merge_request(payload: dict):
    mr = payload.get("object_attributes", {})
    logger.debug(f"GitLab MR: action={mr.get('action')}, id={mr.get('iid')}")
