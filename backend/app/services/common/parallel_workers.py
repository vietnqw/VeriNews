"""
Parallel worker utilities shared across the retrieval and verification pipelines.

Several pipeline stages fan a list of items out across N workers, each of which
makes one or more LLM calls, then merge the results back. This module centralizes
the two pieces that were previously duplicated (with subtle divergences) across
``reranker_service``, ``article_reranker_service`` and ``stance_classifier``:

- :func:`round_robin_batches` splits items across workers so each worker gets an
  even mix, which avoids positional bias from upstream ranking (e.g. vector-search
  order). Every item is paired with its original index so results merge back
  deterministically.
- :func:`run_worker_batches` launches one coroutine per batch and gathers the
  results, capturing (rather than raising) per-worker exceptions so one failed
  worker never aborts the others.

Each caller still owns its own per-worker logic — prompt construction, per-call
timeout policy, and how a failure degrades (fallback score vs. empty dict vs.
NOT_ENOUGH_INFO). That intentional variation is passed in via ``make_worker``.
"""

import asyncio
from typing import Awaitable, Callable, List, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")

#: A batch handed to one worker: a list of (original_index, item) pairs.
IndexedBatch = List[Tuple[int, T]]


def round_robin_batches(
    items: List[T],
    num_workers: int,
    *,
    min_items_for_single_batch: int = 0,
) -> List[IndexedBatch]:
    """Distribute ``items`` across ``num_workers`` batches, preserving indices.

    Batch ``j`` holds every item whose original index ``i`` satisfies
    ``i % num_workers == j``, each stored as an ``(index, item)`` tuple so the
    caller can map scores back to the original ordering.

    Args:
        items: Items to distribute (order preserved within each worker).
        num_workers: Number of batches to produce (>= 1).
        min_items_for_single_batch: If ``0 < len(items) <= this``, all items are
            placed in a single batch (worker 0) so one worker can score them
            comparatively/listwise instead of splitting the comparison across
            workers. Defaults to 0 (always round-robin).

    Returns:
        A list of exactly ``num_workers`` batches. Batches may be empty when
        there are fewer items than workers.
    """
    batches: List[IndexedBatch] = [[] for _ in range(num_workers)]

    if not items:
        return batches

    if 0 < len(items) <= min_items_for_single_batch:
        batches[0] = list(enumerate(items))
        return batches

    for idx, item in enumerate(items):
        batches[idx % num_workers].append((idx, item))

    return batches


async def run_worker_batches(
    batches: List[IndexedBatch],
    make_worker: Callable[[int, IndexedBatch], Awaitable[R]],
) -> List[R]:
    """Run one worker coroutine per batch and gather the results.

    Exceptions from individual workers are captured and returned in-place (via
    ``asyncio.gather(return_exceptions=True)``) rather than propagated, so a
    single failing worker does not cancel the rest. Callers should filter the
    returned list for ``Exception`` instances before use.

    Args:
        batches: Batches produced by :func:`round_robin_batches`.
        make_worker: Factory called as ``make_worker(worker_id, batch)`` that
            returns the awaitable for that worker. Rate limiting (semaphore) and
            per-call timeouts belong inside the worker the caller supplies.

    Returns:
        One result (or ``Exception``) per batch, in worker order.
    """
    tasks = [make_worker(worker_id, batch) for worker_id, batch in enumerate(batches)]
    return await asyncio.gather(*tasks, return_exceptions=True)
