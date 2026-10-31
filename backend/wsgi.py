import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'backend' is always importable
root_dir = str(Path(__file__).resolve().parents[1])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app import create_app

app = create_app()

# Auto-run DB migrations on startup when RUN_MIGRATIONS_ON_STARTUP=true
if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "false").lower() == "true":
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
