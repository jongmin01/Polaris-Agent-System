"""
HPC Tools - Anthropic tool wrappers for hpc_monitor.py and physics_agent.py
"""

import sys
import json
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Graceful imports
_PhysicsMonitor = None
_PhysicsAgent = None
_import_error = None

try:
    from hpc_monitor import PhysicsMonitor
    _PhysicsMonitor = PhysicsMonitor
except Exception as e:
    _import_error = str(e)

try:
    from physics_agent import PhysicsAgent
    _PhysicsAgent = PhysicsAgent
except Exception as e:
    if _import_error is None:
        _import_error = str(e)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "monitor_hpc_job",
        "description": "ALCF Polaris VASP 잡 모니터링. qstat, 수렴 상태 확인.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "PBS job ID on Polaris (e.g. '12345.polaris-pbs-01')"
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to the VASP calculation directory on Polaris (e.g. '/lus/eagle/projects/…/relax')"
                },
                "cluster": {
                    "type": "string",
                    "description": "Optional HPC profile name (e.g. 'polaris', 'carbon'). Defaults to active profile."
                }
            },
            "required": ["job_id", "path"]
        }
    },
    {
        "name": "check_hpc_connection",
        "description": "ALCF Polaris SSH 연결 확인.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "physics_agent_handle",
        "description": "물리 계산 요청. 밴드 구조, DOS, 구조 최적화 등 VASP/ONETEP 입력 파일 생성.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {
                    "type": "string",
                    "description": "Natural language request describing the physics calculation (e.g. 'MoS2 band structure calculation')"
                }
            },
            "required": ["user_message"]
        }
    }
]


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_monitor_hpc_job(job_id: str, path: str, cluster: str = "") -> str:
    """Monitor a VASP job on Polaris."""
    if _PhysicsMonitor is None:
        return json.dumps({"error": f"PhysicsMonitor unavailable: {_import_error}"})
    try:
        monitor = _PhysicsMonitor()
        result = monitor.monitor_job(job_id, path, cluster=cluster or None)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_check_hpc_connection() -> str:
    """Check SSH connection to Polaris."""
    if _PhysicsMonitor is None:
        return json.dumps({"error": f"PhysicsMonitor unavailable: {_import_error}"})
    try:
        monitor = _PhysicsMonitor()
        alive = monitor.zombie_guard()
        return json.dumps({"alive": alive, "message": "Connection alive" if alive else "Connection failed or timed out"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_physics_agent_handle(user_message: str) -> str:
    """Handle a physics calculation request."""
    if _PhysicsAgent is None:
        return json.dumps({"error": f"PhysicsAgent unavailable: {_import_error}"})
    try:
        agent = _PhysicsAgent()
        result = agent.handle(user_message)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Map tool names to handlers
HANDLERS = {
    "monitor_hpc_job": handle_monitor_hpc_job,
    "check_hpc_connection": handle_check_hpc_connection,
    "physics_agent_handle": handle_physics_agent_handle,
}
