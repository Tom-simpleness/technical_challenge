import os
 
SECRET_KEY = "django-insecure-ch4ll3ng3-k3y-d0-n0t-use-in-prod-1234"
 
DEBUG = True
 
ALLOWED_HOSTS = ["*"]
 
ROOT_URLCONF = "config.urls"
 
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "transactions",
]
 
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "challenge_db"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
 
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
 
TIME_ZONE = "UTC"
USE_TZ = True
 
# Celery
_redis_host = os.environ.get("REDIS_HOST", "localhost")
CELERY_BROKER_URL = f"redis://{_redis_host}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{_redis_host}:6379/0"
CELERY_TASK_ALWAYS_EAGER = False
