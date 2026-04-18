import sys
from pathlib import Path

# Setup paths similar to run_heavy.py
skill_dir = Path(__file__).parent
for candidate in ("P:/__csf/src", "P:/__csf", str(skill_dir), "P:/"):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

print("sys.path:")
for p in sys.path[:5]:
    print(f"  {p}")

try:
    import lib.orchestrator as orchestrator
    print("\nSUCCESS: Imported lib.orchestrator")
    print(f"File: {orchestrator.__file__}")
except ImportError as e:
    print(f"\nFAILURE: Could not import lib.orchestrator: {e}")

try:
    from lib.agents.expert import ExpertAgent  # noqa: F401
    print("SUCCESS: Imported ExpertAgent from lib.agents.expert")
except ImportError as e:
    print(f"FAILURE: Could not import ExpertAgent: {e}")

try:
    from lib.models import BrainstormContext  # noqa: F401
    print("SUCCESS: Imported BrainstormContext from lib.models")
except ImportError as e:
    print(f"FAILURE: Could not import BrainstormContext: {e}")
