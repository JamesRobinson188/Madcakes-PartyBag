from flask import Flask
from config import DevConfig
from models import db
from errors import register_error_handlers
from routes_madcakes import bp as madcakes_bp
from routes_partybags import bp as partybags_bp
from agegate import agebp

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(DevConfig)

db.init_app(app)
register_error_handlers(app)

app.register_blueprint(madcakes_bp)
app.register_blueprint(partybags_bp, url_prefix="/party-bags")
app.register_blueprint(agebp)

# in app.py, after app/db setup
@app.before_first_request
def _ensure_db():
    from models import db
    db.create_all()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=81, debug=True)

