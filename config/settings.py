import os
from fastapi.security import HTTPBearer

SECRET_KEY = os.getenv("SECRET_KEY", "yodda-premium-secret-key-change-in-production")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"
ADMIN_SETUP_DONE = False
security = HTTPBearer()
