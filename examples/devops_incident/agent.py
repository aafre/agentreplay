"""DevOps Incident Triage & Remediation Agent.

Demonstrates an operations agent diagnosing service alerts, parsing logs,
verifying remediation policy, and executing safe automated rollouts.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

# Simulated cluster state
CLUSTER_STATE: dict[str, dict[str, Any]] = {
    "auth-service": {
        "status": "degraded",
        "healthy_replicas": 1,
        "desired_replicas": 3,
        "error_rate_pct": 18.5,
        "environment": "production",
    },
    "billing-service": {
        "status": "healthy",
        "healthy_replicas": 4,
        "desired_replicas": 4,
        "error_rate_pct": 0.02,
        "environment": "production",
    },
}

SERVICE_LOGS: dict[str, list[str]] = {
    "auth-service": [
        "2026-08-27T12:01:10Z [ERROR] ThreadPoolExhausted: Unable to acquire connection from pool",
        "2026-08-27T12:01:15Z [FATAL] OOMKilled: Process terminated with exit code 137",
        "2026-08-27T12:01:20Z [WARN] Pod auth-service-7f9b8c6d-x4k9q entering CrashLoopBackOff",
    ],
}


def fetch_service_health(ctx: RunContext[None], service_name: str) -> dict[str, Any]:
    """Retrieve Kubernetes pod metrics and error rates for the target service."""
    service = CLUSTER_STATE.get(service_name.lower())
    if not service:
        return {"error": f"Service '{service_name}' not found in cluster registry"}
    return {"service": service_name, **service}


def fetch_recent_logs(
    ctx: RunContext[None], service_name: str, max_lines: int = 5
) -> dict[str, Any]:
    """Inspect stdout/stderr container logs for fatal exceptions and crashes."""
    logs = SERVICE_LOGS.get(service_name.lower(), ["No recent error events found"])
    return {"service": service_name, "logs": logs[:max_lines]}


def check_remediation_policy(
    ctx: RunContext[None], issue_type: str, environment: str
) -> dict[str, Any]:
    """Verify if automated restart or scaling is permitted under team change policies."""
    # Policy: OOMKilled and Deadlock issues permit automated rolling restarts
    allowed = issue_type.upper() in ("OOMKILLED", "THREADPOOLEXHAUSTED", "DEADLOCK")
    return {
        "issue_type": issue_type,
        "environment": environment,
        "auto_remediation_allowed": allowed,
        "requires_human_approval": not allowed,
    }


def trigger_service_restart(
    ctx: RunContext[None], service_name: str, reason: str
) -> dict[str, Any]:
    """Safely trigger a Kubernetes rolling restart for the target deployment."""
    return {
        "status": "success",
        "action": "rollout restart",
        "target": service_name,
        "message": f"Deployment '{service_name}' restarted successfully. Reason: {reason}",
    }


def create_devops_agent(model: Any = None) -> Agent[None, str]:
    """Factory creating the DevOps incident triage agent."""
    selected_model = model or TestModel(
        call_tools=[
            "fetch_service_health",
            "fetch_recent_logs",
            "check_remediation_policy",
            "trigger_service_restart",
        ]
    )

    return Agent(
        selected_model,
        system_prompt=(
            "You are an on-call DevOps incident response agent. "
            "When responding to production alerts: "
            "1. Fetch the service health to verify degradation. "
            "2. Fetch container logs to diagnose root cause. "
            "3. Check remediation policy before performing actions. "
            "4. If allowed, trigger service restart; otherwise escalate to human on-call."
        ),
        tools=[
            fetch_service_health,
            fetch_recent_logs,
            check_remediation_policy,
            trigger_service_restart,
        ],
    )


if __name__ == "__main__":
    devops_agent = create_devops_agent()
    result = devops_agent.run_sync("Investigate alert: high error rates reported on auth-service")
    print(result.output)
