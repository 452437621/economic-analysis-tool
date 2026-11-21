"""Compatibility wrapper for the old startup catch-up entry point.

The real implementation lives in ``app.jobs.supervisor``: it compares each job
with its planned period, replenishes data first and blocks downstream jobs when
the data is not usable.  Kept as a small module because scripts/tests and older
deployments import ``catch_up_jobs`` from here.
"""

from __future__ import annotations

from app.jobs.plan import JOB_PLANS
from app.jobs.supervisor import catch_up_jobs, run_schedule_check

#: Backwards-compatible view of fixed-time jobs (values are now JobPlan objects).
CATCH_UP = {
    name: plan for name, plan in JOB_PLANS.items() if plan.fixed_time and not plan.manual
}

__all__ = ["CATCH_UP", "catch_up_jobs", "run_schedule_check"]
