import os
from pathlib import Path
from flask import Flask
from config import DevConfig
from models import db
from errors import register_error_handlers
from routes_madcakes import bp as madcakes_bp
from routes_partybags import bp as partybags_bp
from agegate import agebp

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(DevConfig)

# 1) Ensure Azure’s writable directory exists
DATA_DIR = Path("/home/site/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

db.init_app(app)
register_error_handlers(app)

app.register_blueprint(madcakes_bp)
app.register_blueprint(partybags_bp, url_prefix="/party-bags")
app.register_blueprint(agebp)

# 2) Create tables at startup (now the folder exists)
with app.app_context():
    db.create_all()
    # 3) Optional: seed from repo DB once
    seed_src = Path(os.path.dirname(__file__)) / "database" / "products.db"
    seed_dst = DATA_DIR / "products.db"
    if seed_src.exists() and not seed_dst.exists():
        try:
            seed_dst.write_bytes(seed_src.read_bytes())
        except Exception as e:
            # Don’t crash the app if seeding fails
            print(f"[seed] skipped: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81, debug=True)
