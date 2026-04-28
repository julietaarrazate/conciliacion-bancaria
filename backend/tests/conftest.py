"""Configuration for pytest"""

import sys
from pathlib import Path

# Agregar el directorio del backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
