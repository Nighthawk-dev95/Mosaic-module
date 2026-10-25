from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.models.mosaic import (
    BaselineProxyCandidate,
    BaselineProxyDetail,
    BlockerByPractice,
    CapacityBaselineScorecard,
    CapacityPracticeRollup,
    CapacityRadiologistItem,
    CaptureEfficiencyTrendPracticePoint,
    CaptureEfficiencyTrendRadiologistPoint,
    CaptureOverview,
    CapturePracticeRollup,
    CaptureRadiologistItem,
    CaptureUtilizationTrendPracticePoint,
    CaptureUtilizationTrendRadiologistPoint,
    DraftInsightCategoryGroup,
    DraftInsightModalityStat,
    DraftInsightOverview,
    DraftInsightPracticeStat,
    DraftInsightSampleItem,
    EfficiencyDetail,
    EfficiencyFilterOptions,
    EfficiencyTrendPoint,
    EfficiencyTrendRpAvgPoint,
    GenieAskRequest,
    GenieAskResponse,
    GenieMessageResponse,
    MammoScreeningTrendPoint,
    MosaicIntelligenceSnapshot,
    MvpProgramContext,
    MvpRadiologistItem,
    PopulationEfficiency,
    RadiologistRosterItem,
    RadSummaryStat,
    Note,
    RadiologistLookupMatch,
    RadSurveySummary,
    RpceTrendPoint,
    ShiftUtilizationItem,
    UndraftedCategoryPoint,
    UndraftedFilterOptions,
    UtilizationPracticeRollup,
    VolumeFilterOptions,
    VolumeGroupRollup,
    VolumeSummary,
    VolumeTrendPoint,
)
from app.db import postgres_client
from app.services import (
    ai_context_service,
    baseline_overrides,
    cache_service,
    genie_service,
    mvp_weekly_report_service,
    refresh_service,
)

router = APIRouter(prefix="/api/mosaic", tags=["mosaic"])


# Every route below reads from the local SQLite cache (app/services/cache_service.py),
# never from EDW directly - see app/services/refresh_service.py for why: EDW queries here
# were observed to take anywhere from ~2s to 800+s depending on warehouse-side conditions
# outside this app's control, which is unworkable for an interactively-loaded dashboard.
# The cache is populated by a background refresh loop plus the manual /refresh endpoint.


@router.get("/mosaic-intelligence", response_model=MosaicIntelligenceSnapshot)
async def mosaic_intelligence(practice: str | None = None):
    return cache_service.get_mosaic_intelligence_snapshot(practice)


@router.get("/rpce-trend", response_model=list[RpceTrendPoint])
async def rpce_trend(practice: str | None = None):
    return cache_service.get_rpce_trend(practice)


@router.get("/rad-summary-stats", response_model=list[RadSummaryStat])
async def rad_summary_stats(practice: str | None = None, drafting_group: str | None = None):
    return cache_service.get_rad_summary_stats(practice, drafting_group)


@router.get("/roster", response_model=list[RadiologistRosterItem])
async def roster(
    practice: str | None = None,
    subspecialty: str | None = None,
    deployment_status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return cache_service.get_radiologist_roster(practice, subspecialty, deployment_status, limit, offset)


@router.get("/utilization/by-practice", response_model=list[UtilizationPracticeRollup])
async def utilization_by_practice(days_back: int = Query(30, ge=1, le=365)):
    return cache_service.get_utilization_by_practice(days_back)


@router.get("/volume/summary", response_model=VolumeSummary)
async def volume_summary():
    return cache_service.get_volume_summary()


@router.get("/volume/by-practice", response_model=list[VolumeGroupRollup])
async def volume_by_practice():
    return cache_service.get_volume_by_practice()


@router.get("/volume/by-team", response_model=list[VolumeGroupRollup])
async def volume_by_team():
    return cache_service.get_volume_by_team()


@router.get("/volume/by-local-region", response_model=list[VolumeGroupRollup])
async def volume_by_local_region():
    return cache_service.get_volume_by_local_region()


@router.get("/volume/trend", response_model=list[VolumeTrendPoint])
async def volume_trend():
    return cache_service.get_volume_trend()


@router.get("/volume/filters", response_model=VolumeFilterOptions)
async def volume_filters():
    return cache_service.get_volume_filter_options()


@router.get("/blockers/drafting", response_model=list[BlockerByPractice])
async def deployment_blockers_drafting():
    return cache_service.get_drafting_blockers_by_practice()


@router.get("/blockers/ct-abdpel", response_model=list[BlockerByPractice])
async def deployment_blockers_ct_abdpel():
    return cache_service.get_ct_abdpel_blockers_by_practice()


@router.get("/efficiency", response_model=EfficiencyDetail)
async def efficiency_detail(mode: str = Query("full_mosaic")):
    return cache_service.get_efficiency_detail(mode)


@router.get("/efficiency/population", response_model=PopulationEfficiency)
async def efficiency_population(
    mode: str = Query("full_mosaic"),
    practice: str | None = None,
    subspecialty: str | None = None,
    modality_code: str | None = None,
    parent_procedure_name: str | None = None,
    exam_category: str | None = None,
):
    return cache_service.get_efficiency_population(
        mode, practice, subspecialty, modality_code, parent_procedure_name, exam_category
    )


@router.get("/efficiency/filters", response_model=EfficiencyFilterOptions)
async def efficiency_filters():
    return cache_service.get_efficiency_filter_options()


@router.get("/efficiency/trend", response_model=list[EfficiencyTrendPoint])
async def efficiency_trend(exam_category: str | None = None, practice: str | None = None):
    return cache_service.get_efficiency_trend(exam_category, practice)


@router.get("/efficiency/trend/rp-avg", response_model=list[EfficiencyTrendRpAvgPoint])
async def efficiency_trend_rp_avg():
    return cache_service.get_efficiency_trend_rp_avg()


@router.get("/mvp/radiologists", response_model=list[MvpRadiologistItem])
async def mvp_radiologists():
    return cache_service.get_mvp_radiologists()


@router.get("/mvp/context", response_model=MvpProgramContext)
async def mvp_context():
    return cache_service.get_mvp_context()


@router.get("/mvp/area-detail", response_model=dict[str, list[EfficiencyTrendPoint]])
async def mvp_area_detail():
    """All 6 Local teams' 4-line efficiency trend in one call (MVP Area Detail dashboard) -
    there are only 6, and the dropdown needs instant switching between them."""
    return cache_service.get_efficiency_trend_by_local_team()


@router.get("/mvp/mammo-screening-trend", response_model=list[MammoScreeningTrendPoint])
async def mvp_mammo_screening_trend():
    return cache_service.get_mammo_screening_trend()


@router.get("/mvp/mammo-screening-trend/mvp-only", response_model=list[MammoScreeningTrendPoint])
async def mvp_mammo_screening_trend_mvp_only():
    return cache_service.get_mvp_mammo_screening_trend()


@router.post("/mvp/weekly-report/generate")
async def generate_mvp_weekly_report(scope: str = Query(..., pattern="^(overview|mammo)$")):
    # Synchronous LLM call inside (generate_weekly_report_narrative) - must not block the
    # single-threaded event loop, same reasoning as the existing /ai-context route above.
    return await run_in_threadpool(mvp_weekly_report_service.generate_snapshot, scope)


@router.get("/mvp/weekly-report")
async def get_mvp_weekly_report(scope: str = Query(..., pattern="^(overview|mammo)$")):
    snapshots = postgres_client.get_weekly_snapshots(scope, limit=1)
    if not snapshots:
        raise HTTPException(status_code=404, detail=f"No weekly snapshot generated yet for scope={scope!r}")
    return snapshots[0]


@router.get("/mvp/weekly-report/history")
async def get_mvp_weekly_report_history(scope: str = Query(..., pattern="^(overview|mammo)$"), limit: int = Query(12, ge=1, le=52)):
    return postgres_client.get_weekly_snapshots(scope, limit)


@router.get("/mvp/methodology-check")
async def mvp_methodology_check(scope: str = Query(..., pattern="^(overview|mammo)$")):
    return cache_service.get_mvp_methodology_check(scope)


@router.get("/survey/rad-sentiment", response_model=RadSurveySummary)
async def survey_rad_sentiment():
    # Static, hand-compiled from an offline survey export (see app/data/rad_survey.py) -
    # not EDW-derived, so no cache_store/refresh_service involvement, same as rpce_audit.py.
    return cache_service.get_rad_survey_summary()


@router.get("/capture/overview", response_model=CaptureOverview)
async def capture_overview():
    return cache_service.get_capture_overview()


@router.get("/capture/by-practice", response_model=list[CapturePracticeRollup])
async def capture_by_practice(practice: str | None = None):
    return cache_service.get_capture_by_practice(practice)


@router.get("/capture/by-radiologist", response_model=list[CaptureRadiologistItem])
async def capture_by_radiologist(practice: str | None = None):
    return cache_service.get_capture_by_radiologist(practice)


@router.get("/capture/trend/utilization/by-practice", response_model=list[CaptureUtilizationTrendPracticePoint])
async def capture_trend_utilization_by_practice(
    granularity: str = Query("week", pattern="^(week|month)$"), practice: str | None = None
):
    return cache_service.get_capture_utilization_trend_by_practice(granularity, practice)


@router.get("/capture/trend/utilization/by-radiologist", response_model=list[CaptureUtilizationTrendRadiologistPoint])
async def capture_trend_utilization_by_radiologist(
    granularity: str = Query("week", pattern="^(week|month)$"),
    practice: str | None = None,
    npi: int | None = None,
):
    return cache_service.get_capture_utilization_trend_by_radiologist(granularity, practice, npi)


@router.get("/capture/trend/efficiency/by-practice", response_model=list[CaptureEfficiencyTrendPracticePoint])
async def capture_trend_efficiency_by_practice(
    granularity: str = Query("week", pattern="^(week|month)$"), practice: str | None = None
):
    return cache_service.get_capture_efficiency_trend_by_practice(granularity, practice)


@router.get("/capture/trend/efficiency/by-radiologist", response_model=list[CaptureEfficiencyTrendRadiologistPoint])
async def capture_trend_efficiency_by_radiologist(
    granularity: str = Query("week", pattern="^(week|month)$"),
    practice: str | None = None,
    npi: int | None = None,
):
    return cache_service.get_capture_efficiency_trend_by_radiologist(granularity, practice, npi)


@router.get("/capacity/by-radiologist", response_model=list[CapacityRadiologistItem])
async def capacity_by_radiologist(limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return cache_service.get_capacity_by_radiologist(limit, offset)


@router.get("/capacity/by-practice", response_model=list[CapacityPracticeRollup])
async def capacity_by_practice():
    return cache_service.get_capacity_by_practice()


@router.get("/shift-utilization", response_model=list[ShiftUtilizationItem])
async def shift_utilization(practice: str | None = None):
    return cache_service.get_shift_utilization_by_radiologist(practice)


@router.get("/undrafted-analysis", response_model=list[UndraftedCategoryPoint])
async def undrafted_analysis(practice: str | None = None, exam_category: str | None = None, site: str | None = None):
    return cache_service.get_undrafted_analysis(practice, exam_category, site)


@router.get("/undrafted-analysis/filters", response_model=UndraftedFilterOptions)
async def undrafted_analysis_filters():
    return cache_service.get_undrafted_filter_options()


@router.get("/draft-insights/overview", response_model=DraftInsightOverview)
async def draft_insights_overview():
    return cache_service.get_draft_insight_overview()


@router.get("/draft-insights/by-modality", response_model=list[DraftInsightModalityStat])
async def draft_insights_by_modality():
    return cache_service.get_draft_insight_by_modality()


@router.get("/draft-insights/by-practice", response_model=list[DraftInsightPracticeStat])
async def draft_insights_by_practice():
    return cache_service.get_draft_insight_by_practice()


@router.get("/draft-insights/categories", response_model=list[DraftInsightCategoryGroup])
async def draft_insights_categories():
    return cache_service.get_draft_insight_categories()


@router.get("/draft-insights/samples", response_model=list[DraftInsightSampleItem])
async def draft_insights_samples(overall_assessment: str | None = None, limit: int = Query(50, ge=1, le=500)):
    return cache_service.get_draft_insight_samples(overall_assessment, limit)


@router.get("/capacity/baseline-scorecard", response_model=list[CapacityBaselineScorecard])
async def capacity_baseline_scorecard():
    return cache_service.get_capacity_baseline_scorecard()


@router.get("/capacity/baseline-proxy-detail", response_model=list[BaselineProxyDetail])
async def capacity_baseline_proxy_detail(practice: str | None = None):
    return cache_service.get_baseline_proxy_detail(practice)


@router.get("/capacity/baseline-proxy-candidates", response_model=list[BaselineProxyCandidate])
async def capacity_baseline_proxy_candidates(npi: int | None = None, target_shift: str | None = None):
    return cache_service.get_baseline_proxy_candidates(npi, target_shift)


class BaselineReviewDecisionIn(BaseModel):
    npi: int
    target_shift: str
    status: str
    chosen_proxy_shift: str | None = None
    chosen_rank: int | None = None
    note: str | None = None


@router.get("/capacity/baseline-review-decisions")
async def get_baseline_review_decisions():
    # Durable on the dev-bhargav Lakebase Postgres branch (app/db/postgres_client.py), same
    # resource as /refresh/history - empty list if Postgres is unavailable, never an error.
    return postgres_client.list_review_decisions()


@router.post("/capacity/baseline-review-decisions")
async def post_baseline_review_decision(decision: BaselineReviewDecisionIn):
    saved = postgres_client.save_review_decision(
        npi=decision.npi,
        target_shift=decision.target_shift,
        status=decision.status,
        chosen_proxy_shift=decision.chosen_proxy_shift,
        chosen_rank=decision.chosen_rank,
        note=decision.note,
        reviewed_at=datetime.now(timezone.utc),
    )
    if saved:
        # Closes the loop live, not just on the next 30-min refresh - this is what makes
        # accepting/overriding a review actually change the Capacity tab within seconds.
        try:
            baseline_overrides.recompute_capacity_with_overrides()
        except Exception as exc:  # noqa: BLE001 - the decision is already saved either way
            print(f"[baseline-review] recompute_capacity_with_overrides failed: {exc}", flush=True)
    return {"saved": saved}


@router.get("/capacity/review-activity")
async def get_review_activity(limit: int = Query(20, ge=1, le=100)):
    """Enriches the raw decision log with each decision's real capacity-rate impact (chosen
    candidate's rate minus the algorithm's own rank-1 rate) - powers the Baseline Review
    Queue's live activity ticker. Computed on read, not stored, so it's always consistent with
    whatever's currently cached in baseline_proxy_candidates_raw."""
    decisions = postgres_client.list_review_decisions()[:limit]
    enriched = []
    for d in decisions:
        candidates = cache_service.get_baseline_proxy_candidates(d["npi"], d["target_shift"])
        by_rank = {c.rank: c for c in candidates}
        default_candidate = by_rank.get(1)
        chosen_candidate = by_rank.get(d.get("chosen_rank")) if d.get("chosen_rank") else None
        impact = None
        if d["status"] != "rejected_no_match" and default_candidate and chosen_candidate:
            default_rate = default_candidate.baseline_tbwu_per_hour
            chosen_rate = chosen_candidate.baseline_tbwu_per_hour
            if default_rate is not None and chosen_rate is not None:
                impact = chosen_rate - default_rate
        anchor = chosen_candidate or default_candidate
        enriched.append(
            {
                **d,
                "radiologist_name": anchor.radiologist_name if anchor else None,
                "practice": anchor.practice if anchor else None,
                "capacity_impact_tbwu_per_hour": impact,
            }
        )
    return enriched


@router.get("/radiologist-lookup/search", response_model=list[RadiologistLookupMatch])
async def search_radiologist_lookup(q: str = Query(...)):
    # 3-character minimum, matching PCC's own radiologist-drilldown search gate exactly -
    # not a soft UX hint, a real server-side floor.
    if len(q.strip()) < 3:
        raise HTTPException(status_code=400, detail="Search query must be at least 3 characters")
    return cache_service.search_radiologist_lookup(q)


@router.get("/radiologist-lookup/{npi}")
async def get_radiologist_lookup(npi: int, q: str | None = Query(None)):
    # The actual privacy-log step - every open of this page writes an audit row, mirroring
    # PCC's own "views are still logged" rule for this exact kind of individual drilldown.
    postgres_client.log_radiologist_lookup_view(npi, q, datetime.now(timezone.utc))
    return cache_service.get_radiologist_lookup_detail(npi)


class AiContextRequest(BaseModel):
    feature: str
    entity_label: str
    metric_label: str
    value: str
    extra: dict[str, str] | None = None


class AiContextResponse(BaseModel):
    explanation: str


@router.post("/ai-context", response_model=AiContextResponse)
async def ai_context(req: AiContextRequest):
    # explain_data_point makes a synchronous, potentially slow (cold-start, auth-scope-retry,
    # or just a loaded serving endpoint) network call - confirmed live this session to otherwise
    # freeze the entire single-threaded ASGI event loop (every other concurrent request, on any
    # route, stalls until it returns) if called directly from an async route. run_in_threadpool
    # keeps this endpoint's own fail-closed contract (still never raises) while no longer being
    # able to take the rest of the app down with it.
    explanation = await run_in_threadpool(
        ai_context_service.explain_data_point,
        req.feature, req.entity_label, req.metric_label, req.value, req.extra,
    )
    return AiContextResponse(explanation=explanation)


@router.post("/genie/ask", response_model=GenieAskResponse)
async def genie_ask(req: GenieAskRequest):
    result = genie_service.ask(req.question, req.conversation_id)
    return GenieAskResponse(**result)


@router.get("/genie/message", response_model=GenieMessageResponse)
async def genie_message(conversation_id: str, message_id: str):
    result = genie_service.get_message(conversation_id, message_id)
    return GenieMessageResponse(**result)


class NoteIn(BaseModel):
    entity_type: str
    entity_key: str
    note_text: str


@router.get("/notes", response_model=list[Note])
async def get_notes(entity_type: str = Query(...), entity_key: str = Query(...)):
    return postgres_client.list_notes(entity_type, entity_key)


@router.post("/notes")
async def post_note(note: NoteIn):
    if note.entity_type not in ("radiologist", "practice"):
        raise HTTPException(status_code=400, detail="entity_type must be 'radiologist' or 'practice'")
    saved = postgres_client.save_note(
        entity_type=note.entity_type,
        entity_key=note.entity_key,
        note_text=note.note_text,
        created_at=datetime.now(timezone.utc),
    )
    if not saved:
        raise HTTPException(status_code=503, detail="Could not save note - Postgres unavailable")
    return {"status": "saved"}


@router.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Kick off an EDW refresh in the background and return immediately - this can take
    several minutes to tens of minutes depending on warehouse conditions."""
    background_tasks.add_task(refresh_service.refresh_all)
    return {"status": "refresh started"}


@router.get("/refresh/status")
async def get_refresh_status():
    return refresh_service.refresh_status()


@router.get("/refresh/history")
async def get_refresh_history(limit: int = Query(100, ge=1, le=500)):
    # Durable log on the dev-bhargav Lakebase Postgres branch (app/db/postgres_client.py) -
    # separate from /refresh/status above, which stays in-memory/SQLite and is lost on restart.
    return postgres_client.recent_refresh_log(limit)
