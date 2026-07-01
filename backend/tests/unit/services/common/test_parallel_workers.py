"""
Unit tests for the shared parallel-worker helpers.

Covers round-robin batching (distribution, index preservation, adaptive
single-batch, empty input) and the fan-out helper (results in order,
per-worker exceptions captured not raised).
"""

import pytest

from app.services.common import round_robin_batches, run_worker_batches


@pytest.mark.unit
class TestRoundRobinBatches:
    def test_distributes_evenly_across_workers(self):
        batches = round_robin_batches(["a", "b", "c", "d", "e"], 2)
        assert len(batches) == 2
        # worker 0 gets indices 0,2,4 ; worker 1 gets 1,3
        assert batches[0] == [(0, "a"), (2, "c"), (4, "e")]
        assert batches[1] == [(1, "b"), (3, "d")]

    def test_preserves_original_indices(self):
        items = ["x", "y", "z"]
        batches = round_robin_batches(items, 3)
        recovered = {idx: val for batch in batches for idx, val in batch}
        assert recovered == {0: "x", 1: "y", 2: "z"}

    def test_empty_input_returns_empty_batches(self):
        batches = round_robin_batches([], 3)
        assert batches == [[], [], []]

    def test_fewer_items_than_workers(self):
        batches = round_robin_batches(["a"], 4)
        assert batches[0] == [(0, "a")]
        assert all(len(b) == 0 for b in batches[1:])

    def test_adaptive_single_batch_when_below_threshold(self):
        # 3 items <= threshold 4 => all go to worker 0 for comparative scoring
        batches = round_robin_batches(["a", "b", "c"], 8, min_items_for_single_batch=4)
        assert batches[0] == [(0, "a"), (1, "b"), (2, "c")]
        assert all(len(b) == 0 for b in batches[1:])

    def test_round_robin_when_above_single_batch_threshold(self):
        # 6 items > threshold 4 => round-robin, not single batch
        batches = round_robin_batches(list(range(6)), 2, min_items_for_single_batch=4)
        assert batches[0] == [(0, 0), (2, 2), (4, 4)]
        assert batches[1] == [(1, 1), (3, 3), (5, 5)]


@pytest.mark.unit
class TestRunWorkerBatches:
    async def test_returns_results_in_worker_order(self):
        batches = round_robin_batches(["a", "b", "c", "d"], 2)

        async def worker(worker_id, batch):
            return (worker_id, len(batch))

        results = await run_worker_batches(batches, worker)
        assert results == [(0, 2), (1, 2)]

    async def test_captures_exceptions_without_raising(self):
        batches = round_robin_batches(["a", "b"], 2)

        async def worker(worker_id, batch):
            if worker_id == 1:
                raise ValueError("boom")
            return "ok"

        results = await run_worker_batches(batches, worker)
        assert results[0] == "ok"
        assert isinstance(results[1], ValueError)
