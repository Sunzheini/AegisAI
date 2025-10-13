import os


APP_NAME = "api-gateway-service"
ALLOWED_CONTENT_TYPES_SET = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "video/mp4",
    "application/pdf",
}
MAX_UPLOAD_BYTES_SIZE = 50 * 1024 * 1024
RATE_LIMIT_PER_MINUTE = 60

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(BASE_DIR, 'app.log')
