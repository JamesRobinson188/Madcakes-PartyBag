from flask import Flask
from config import DevConfig
from models import db
from routes_madcakes import bp as madcakes_bp
from routes_partybags import bp as partybags_bp
from agegate import agebp
import logging, os

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(DevConfig)

logging.basicConfig(level=logging.INFO)
app.logger.handlers = logging.getLogger().handlers
app.logger.setLevel(logging.INFO)

db.init_app(app)

app.register_blueprint(madcakes_bp)
app.register_blueprint(partybags_bp, url_prefix="/party-bags")
app.register_blueprint(agebp)

@app.get("/healthz")
def healthz():
    return "ok", 200

# Safe DB init at startup
with app.app_context():
    try:
        os.makedirs("/home/site/data", exist_ok=True)
        db.create_all()
        app.logger.info("DB ready at %s", app.config["SQLALCHEMY_DATABASE_URI"])
    except Exception as e:
        app.logger.exception("DB init failed: %s", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81, debug=True)
