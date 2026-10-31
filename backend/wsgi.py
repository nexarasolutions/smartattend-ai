import os
from backend.app import create_app

app = create_app()

# Auto-run DB migrations on startup when RUN_MIGRATIONS_ON_STARTUP=true
# Set this env var to "true" on Render for the first deploy, then remove it.
if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "false").lower() == "true":
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
