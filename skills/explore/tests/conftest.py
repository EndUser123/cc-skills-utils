"""pytest configuration for /explore skill tests.

Sets up the import path so that 'skills.explore' can be imported correctly.
"""

import sys
import warnings
from pathlib import Path

# Suppress requests dependency warning (chardet 7.x vs expected <6.x)
# This warning is cosmetic - charset_normalizer is used as fallback
try:
    from requests.exceptions import RequestsDependencyWarning

    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass  # Older requests versions may not have this exception

# Add the .claude directory to sys.path so 'skills.explore' imports work
# pytest rootdir is P:\.claude, but we need to add it to sys.path
claude_root = Path(__file__).parent.parent.parent.parent
if str(claude_root) not in sys.path:
    sys.path.insert(0, str(claude_root))
