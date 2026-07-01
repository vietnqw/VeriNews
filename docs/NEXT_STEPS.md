# VeriNews — Next Steps

This document is the forward-looking roadmap: what remains to make VeriNews a
complete, credible, portfolio-quality system. It is ordered by impact for an
AI-engineer / research portfolio, so the **evaluation harness leads** — without it,
none of the pipeline's quality claims are measurable.

Items here are **not yet implemented**. A separate cleanup pass has already landed
(shared parallel-worker utilities, memoized settings + startup config validation,
an article repository seam, config-driven thresholds, a deduplicated verification
API, and an extension cleanup) — see the git history on `refactor/cleanup-and-roadmap`.

---

## 0. Flagship — ML Evaluation Harness

**Why first:** VeriNews makes strong quality claims (hybrid retrieval, LLM
reranking, multi-signal confidence, NLI verdicts) but currently has **no way to
measure whether any of it works or whether each stage earns its cost**. An
evaluation harness is the single highest-signal addition for a research/AI CV: it
turns "I built a pipeline" into "I built a pipeline and measured it at X."

### 0.1 Benchmark dataset
- Assemble **~300–500 Vietnamese posts** with human-annotated ground truth:
  overall verdict (`FULLY_SUPPORTED` / `PARTIALLY_SUPPORTED` / `REFUTED` /
  `NOT_ENOUGH_INFO`) and, per post, the set of articles that are genuinely
  relevant (for retrieval scoring).
- Version it (e.g. `eval/datasets/vi_verify_v1/`) with a datasheet: sources,
  labeling guidelines, inter-annotator agreement, class balance, date range.
- Include hard cases on purpose: satire, opinion, partially-true claims,
  stale-but-related articles, entity collisions (same name, different event).

### 0.2 Retrieval metrics
- **Recall@k** (k = 5/10/20), **MRR**, and **nDCG@10** against annotated relevant
  articles, computed at the article level (post-aggregation).
- Report per-stage: after fusion, after chunk rerank, after article rerank — so
  the recall/precision trade-off of each stage is visible.

### 0.3 Verification metrics
- **Post-level** accuracy and **macro-F1** over the four verdict classes, plus a
  confusion matrix (the interesting failures are REFUTED↔NOT_ENOUGH_INFO).
- **Claim-level** accuracy where claim annotations exist.
- Stance-classification accuracy against a labeled claim–article subset.

### 0.4 Confidence calibration
- Does `confidence` track actual correctness? Compute **ECE** and plot a
  **reliability diagram** for both retrieval confidence and verification confidence.
- This directly validates (or refutes) the multi-signal confidence scoring that the
  pipeline already computes but never checks.

### 0.5 Baselines & ablations
- **Baselines:** BM25-only, vector-only, and hybrid (to show hybrid earns its
  complexity); a keyword-overlap verdict baseline (to show NLI earns its cost).
- **Ablations:** pipeline with/without chunk reranking, entity filter, article
  reranking, confidence gating, and the fallback ("related mode") pass. Quantify
  the metric delta each contributes — this is the core research story.

### 0.6 Tooling
- An `eval/` package + a `verinews eval run` CLI command (extend the existing Typer
  CLI in `backend/scripts/cli/`).
- **Experiment tracking** via MLflow or Weights & Biases: log config snapshot,
  dataset version, and all metrics per run so results are reproducible and
  comparable across changes.
- An **error-analysis** notebook/report that buckets failures (retrieval miss vs.
  stance error vs. aggregation error vs. calibration error).

**Deliverable that sells the project:** a short `docs/EVALUATION.md` with a metrics
table, the reliability diagram, and the ablation results.

---

## 1. Legacy test-suite repair

The suite has ~37 pre-existing failing tests that predate later code changes (they
are **not** regressions from the cleanup pass — the refactor was verified
regression-free against the baseline). They need rewriting to current behavior:

- **`test_article_aggregation_service.py`** (~16): assert an obsolete *sum-of-scores*
  strategy and call the async method without `await`. Rewrite for the current
  *max-chunk-score* strategy and `min_chunk_score` article filtering.
- **`test_retrieval_orchestrator.py`** (~10): use `MagicMock` where `AsyncMock` is
  required, so awaited pipeline calls fail. Fix the mock types.
- **`test_rss_service.py`** (~7): feedparser/entity-decoding drift — verify against
  the current parser behavior.
- **`test_health.py`** (~3) and **`test_verification.py`** (1, stale `reasoning` key):
  update assertions to the current response shape.
- **`test_reranker_service.py`** (2): decide intended behavior when *all* rerank
  workers fail — return sub-threshold fallback chunks, or empty? Then align the test.
- Re-enable the coverage gate (`--cov-fail-under`, currently commented out in
  `pytest.ini`) once green, and add the `pyvi` `SyntaxWarning` to `filterwarnings`
  so a cold `.pyc` cache doesn't break collection.

## 2. CI/CD & quality gates

- **GitHub Actions**: run `ruff check` + `ruff format --check` + `pytest` with
  coverage on every PR; upload the coverage report.
- Add **type checking** (mypy or pyright) — the codebase is largely typed already.
- Expand pre-commit (it currently runs ruff only): add mypy and a basic security
  check (e.g. `bandit`/`pip-audit`).

## 3. Deployment

- A backend **`Dockerfile`** and a full-stack `docker-compose` (app + Postgres +
  Redis + workers), so the whole system starts with one command.
- Production server config (gunicorn/uvicorn workers — the `prod` CLI command
  exists but there is no container image), reverse-proxy/TLS notes.
- A `docs/DEPLOYMENT.md` runbook (env config, scaling the crawler workers, backups).

## 4. API & security

- **Auth**: API-key validation + per-client **rate limiting** on `/api/v1/verify`
  (currently open).
- Tighten **CORS** off `["*"]` for non-local environments.
- The request schema already caps post length (10–10000 chars); document the public
  OpenAPI surface and the SSE event contract.

## 5. Observability

- **Sentry** for error tracking; **Prometheus** metrics (the pipeline already
  records per-stage timings and persists them to `retrieval_results` — export them).
- Structured request tracing (correlate a verify request across retrieval +
  verification stages).

## 6. Extension robustness & i18n

- **Resilient extraction**: the Facebook DOM selectors in `extractor.js` are
  brittle (hard-coded class names, `div[dir="auto"]`). Add multi-strategy
  extraction with graceful degradation and a self-test against saved DOM fixtures.
- **Full i18n**: a `strings.js` table for all user-facing Vietnamese text. The
  cleanup pass deduplicated the SSE parsing and removed dead code, but `ui.js`
  (~890 lines) still holds inline strings; extracting them safely needs a live
  Chrome + Facebook session to verify the UI, so it was deliberately deferred.
- Scope the `MutationObserver` more narrowly than `document.body` for performance on
  large feeds; add extension versioning/auto-update notes.

## 7. Data & sources

- Enforce the configured **retention window** automatically (config exists;
  scheduled cleanup should act on it) and add **feed-health monitoring** (dead RSS
  feeds, empty parses).
- Broaden the source set and de-duplicate feeds across sources in `sources.yaml`.

## 8. Documentation

- `CONTRIBUTING.md`, a troubleshooting guide, and an architecture + evaluation
  write-up suitable to link from a CV.
- Fix README drift (it lists a Backend README / Testing Guide that don't exist, and
  marks the extension phase as pending though it is largely built).
