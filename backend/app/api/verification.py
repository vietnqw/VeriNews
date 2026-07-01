"""
Verification API Endpoints

Provides endpoints for verifying Facebook posts using the retrieval pipeline.
"""

import asyncio
import json
import time
from typing import Dict
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._verification_serde import (
    build_cache_hit_response,
    build_fresh_response,
    verification_result_to_cache_dict,
)
from app.config.database import get_db
from app.core.logging import get_logger
from app.schemas.verification import (
    VerificationRequest,
    VerificationResponse,
)
from app.services.cache.retrieval_cache import RetrievalCache
from app.services.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from app.services.verification.verification_service import VerificationService

logger = get_logger(__name__)

router = APIRouter(prefix="/verify", tags=["verification"])

# Vietnamese stage names for user-friendly progress display
STAGE_NAMES = {
    "query_extraction": "Xử lý nội dung bài đăng, trích xuất luận điểm chính",
    "search": "Tìm kiếm bài báo liên quan",
    "evaluation": "Đánh giá độ tin cậy của các luận điểm dựa vào các bài báo liên quan",
    "synthesis": "Tổng hợp kết quả",
}


def create_stage_event(stage_key: str, status: str = "in_progress") -> Dict:
    """Create a stage progress event."""
    stage_name = STAGE_NAMES.get(stage_key, stage_key)
    return {
        "type": "stage_update",
        "stage": stage_key,
        "stage_name": stage_name,
        "status": status,
        "timestamp": time.time(),
    }


def _parse_or_generate_uuid(value: str) -> UUID:
    """
    Parse UUID from string or generate a deterministic UUID from invalid string.

    Args:
        value: String to parse as UUID

    Returns:
        UUID object
    """
    if not value:
        return UUID(int=0)

    try:
        return UUID(value)
    except (ValueError, TypeError):
        # Generate deterministic UUID from string hash
        # Using DNS namespace for consistency
        return uuid5(UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), value)


async def _verify_post_standard(
    request: VerificationRequest,
    db: AsyncSession,
) -> VerificationResponse:
    """
    Standard (non-streaming) verification endpoint.
    """
    try:
        logger.info(f"Verification request received: {request.text[:100]}...")
        request_start_time = time.time()

        # Initialize cache
        cache = RetrievalCache()

        # Check cache first (unless cache_bypass is True)
        if not request.cache_bypass:
            cached_result = await cache.get(request.text)
            if cached_result:
                logger.info("Returning cached result")
                total_elapsed_ms = int((time.time() - request_start_time) * 1000)
                return build_cache_hit_response(cached_result, total_elapsed_ms)
        else:
            logger.info("Cache bypass requested, forcing re-verification")

        # Run retrieval pipeline
        orchestrator = RetrievalOrchestrator(db)
        result = await orchestrator.retrieve(request.text)

        # Convert ArticleResult objects to dicts
        articles_dict = [article.to_dict() for article in result["articles"]]

        # Run verification pipeline
        verification_service = VerificationService()
        verification_result, verification_timings = await verification_service.verify(
            post_text=request.text,
            claims=result.get("claims", []),
            articles=result["articles"],
        )

        # Cache the result (including all retrieval and verification metadata)
        await cache.set(
            post_text=request.text,
            articles=result["articles"],
            total_time_ms=result["total_time_ms"],
            stage_timings=result["stage_timings"],
            query_count=result["query_count"],
            claims=result.get("claims", []),
            factual_confidence=result.get("factual_confidence"),
            retrieval_confidence=result.get("retrieval_confidence"),
            confidence_metrics=result.get("confidence_metrics"),
            low_confidence_warning=result.get("low_confidence_warning", False),
            early_exit=result.get("early_exit", False),
            exit_reason=result.get("exit_reason"),
            message=result.get("message"),
            verification_result=verification_result_to_cache_dict(verification_result),
        )

        # Merge stage timings
        stage_timings = result["stage_timings"]
        stage_timings.update(verification_timings)

        # Total time from request start (includes retrieval + verification)
        total_elapsed_ms = int((time.time() - request_start_time) * 1000)

        return build_fresh_response(
            result,
            articles_dict,
            verification_result,
            stage_timings,
            total_elapsed_ms,
        )

    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Verification failed: {str(e)}"
        ) from e


def _verify_post_streaming(
    request: VerificationRequest,
    db: AsyncSession,
):
    """
    Streaming (SSE) verification endpoint that emits stage progress events.
    """

    async def event_generator():
        """Generator that yields SSE events as stages complete."""
        try:
            request_start_time = time.time()

            logger.info(
                f"Streaming verification request received: {request.text[:100]}..."
            )

            # Initialize cache
            cache = RetrievalCache()

            # Emit stage 1: Query extraction start
            event = create_stage_event("query_extraction", "in_progress")
            yield f"data: {json.dumps(event)}\n\n"

            # Check cache first
            if not request.cache_bypass:
                cached_result = await cache.get(request.text)
                if cached_result:
                    logger.info("Returning cached result (streaming)")
                    # Emit all stages as completed for cache hits
                    for stage in [
                        "query_extraction",
                        "search",
                        "evaluation",
                        "synthesis",
                    ]:
                        event = create_stage_event(stage, "completed")
                        yield f"data: {json.dumps(event)}\n\n"

                    # Emit final result
                    total_elapsed_ms = int((time.time() - request_start_time) * 1000)
                    response = build_cache_hit_response(cached_result, total_elapsed_ms)
                    yield f"data: {json.dumps({'type': 'result', 'data': response.model_dump()})}\n\n"
                    return

            # Run retrieval with stage progress
            logger.info("Cache miss or bypass, running full pipeline (streaming)")

            # Emit: Stage 1 starting (Query extraction)
            event = create_stage_event("query_extraction", "in_progress")
            yield f"data: {json.dumps(event)}\n\n"

            # Create a queue for real-time stage events
            stage_queue = asyncio.Queue()

            # Callback for orchestrator stage emissions
            async def on_stage_complete(stage_name: str):
                """Queue stage completion event for immediate streaming."""
                event = create_stage_event(stage_name, "completed")
                await stage_queue.put(event)

            # Create orchestrator with callback
            orchestrator = RetrievalOrchestrator(
                db, on_stage_complete=on_stage_complete
            )

            # Run retrieval and emit stage events concurrently
            async def run_retrieval():
                """Run the retrieval pipeline."""
                return await orchestrator.retrieve(request.text)

            # Start retrieval task
            retrieval_task = asyncio.create_task(run_retrieval())

            # Emit stage events as they arrive (with timeout to not block forever)
            result = None
            while result is None:
                try:
                    # Try to get a stage event with short timeout
                    event = await asyncio.wait_for(stage_queue.get(), timeout=0.5)
                    yield f"data: {json.dumps(event)}\n\n"

                    # If query extraction just completed, start search next
                    if (
                        event.get("stage") == "query_extraction"
                        and event.get("status") == "completed"
                    ):
                        event = create_stage_event("search", "in_progress")
                        yield f"data: {json.dumps(event)}\n\n"

                    # If search just completed, start evaluation next
                    elif (
                        event.get("stage") == "search"
                        and event.get("status") == "completed"
                    ):
                        event = create_stage_event("evaluation", "in_progress")
                        yield f"data: {json.dumps(event)}\n\n"

                except asyncio.TimeoutError:
                    # Check if retrieval is done
                    if retrieval_task.done():
                        # Get any remaining events and then finish
                        while not stage_queue.empty():
                            event = stage_queue.get_nowait()
                            yield f"data: {json.dumps(event)}\n\n"
                        result = await retrieval_task
                    # Otherwise continue waiting
                    continue

            articles_dict = [article.to_dict() for article in result["articles"]]

            verification_service = VerificationService()
            (
                verification_result,
                verification_timings,
            ) = await verification_service.verify(
                post_text=request.text,
                claims=result.get("claims", []),
                articles=result["articles"],
            )

            event = create_stage_event("evaluation", "completed")
            yield f"data: {json.dumps(event)}\n\n"

            # Stage 4: Synthesis start and complete
            event = create_stage_event("synthesis", "in_progress")
            yield f"data: {json.dumps(event)}\n\n"

            await cache.set(
                post_text=request.text,
                articles=result["articles"],
                total_time_ms=result["total_time_ms"],
                stage_timings=result["stage_timings"],
                query_count=result["query_count"],
                claims=result.get("claims", []),
                factual_confidence=result.get("factual_confidence"),
                retrieval_confidence=result.get("retrieval_confidence"),
                confidence_metrics=result.get("confidence_metrics"),
                low_confidence_warning=result.get("low_confidence_warning", False),
                early_exit=result.get("early_exit", False),
                exit_reason=result.get("exit_reason"),
                message=result.get("message"),
                verification_result=verification_result_to_cache_dict(
                    verification_result
                ),
            )

            event = create_stage_event("synthesis", "completed")
            yield f"data: {json.dumps(event)}\n\n"

            # Merge stage timings
            stage_timings = result["stage_timings"]
            stage_timings.update(verification_timings)

            total_elapsed_ms = int((time.time() - request_start_time) * 1000)

            response = build_fresh_response(
                result,
                articles_dict,
                verification_result,
                stage_timings,
                total_elapsed_ms,
            )

            yield f"data: {json.dumps({'type': 'result', 'data': response.model_dump()})}\n\n"

        except Exception as e:
            logger.error(f"Error during streaming verification: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("")
async def verify_post(
    request: VerificationRequest,
    db: AsyncSession = Depends(get_db),
    stream: bool = Query(
        False, description="Enable server-sent events for stage progress"
    ),
):
    """
    Verify a Facebook post by retrieving relevant articles.

    This endpoint supports two modes:
    1. Standard mode (stream=False): Returns complete response immediately
    2. Streaming mode (stream=True): Returns SSE events showing progress, then final result

    Args:
        request: VerificationRequest with post text
        db: Database session (dependency injection)
        stream: Enable SSE streaming for stage progress

    Returns:
        If stream=False: VerificationResponse object
        If stream=True: StreamingResponse with SSE events
    """
    if stream:
        return _verify_post_streaming(request, db)
    else:
        return await _verify_post_standard(request, db)
