import os, yaml
from dotenv import load_dotenv

load_dotenv()

def load_config(name: str) -> dict:
    with open(f"config/{name}.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"{key} not set in .env")
    return val
