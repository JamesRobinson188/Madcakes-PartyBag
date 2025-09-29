import os
from dotenv import load_dotenv
load_dotenv()  # fine locally; harmless in Azure

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # FOUR slashes for an absolute sqlite path:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:////home/site/data/products.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")

class DevConfig(BaseConfig):
    DEBUG = True
