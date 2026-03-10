"""Enterprise DevEx Orchestrator generated FastAPI application."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

APP_NAME = "intent-legal-contract-review"
VERSION = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(APP_NAME)

app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description="Legal Contract Review and Redlining API",
    docs_url="/docs",
    redoc_url=None,
)


def get_keyvault_client() -> SecretClient:
    """Create an authenticated Key Vault client using Managed Identity."""
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID")
    )
    vault_uri = os.getenv("KEY_VAULT_URI", "")
    if vault_uri:
        return SecretClient(vault_url=vault_uri, credential=credential)

    vault_name = os.getenv("KEY_VAULT_NAME", "")
    if not vault_name:
        raise ValueError("Set KEY_VAULT_URI or KEY_VAULT_NAME")
    return SecretClient(vault_url=f"https://{vault_name}.vault.azure.net", credential=credential)


def get_blob_client() -> BlobServiceClient:
    """Create an authenticated Blob Storage client using Managed Identity."""
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID")
    )
    account_url = os.getenv("STORAGE_ACCOUNT_URL", "")
    if not account_url:
        raise ValueError("STORAGE_ACCOUNT_URL environment variable not set")
    return BlobServiceClient(account_url=account_url, credential=credential)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>{APP_NAME}</title>
      <style>
        body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f3f6fb; }}
        .wrap {{ max-width: 760px; margin: 48px auto; background: #fff; padding: 28px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.08); }}
        h1 {{ margin-top: 0; color: #0f6cbd; }}
        .links a {{ display: inline-block; margin: 8px 8px 0 0; padding: 10px 14px; background: #0f6cbd; color: #fff; text-decoration: none; border-radius: 8px; }}
      </style>
    </head>
    <body>
      <div class=\"wrap\">
        <h1>{APP_NAME}</h1>
        <p>Status: running</p>
        <p>Version: {VERSION}</p>
        <div class=\"links\">
          <a href=\"/docs\">API docs</a>
          <a href=\"/health\">Health</a>
          <a href=\"/keyvault/status\">Key Vault status</a>
          <a href=\"/storage/status\">Storage status</a>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/keyvault/status")
async def keyvault_status():
    try:
        client = get_keyvault_client()
        list(client.list_properties_of_secrets(max_page_size=1))
        return {"status": "connected", "vault_accessible": True}
    except Exception as exc:
        logger.error("Key Vault health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})


@app.get("/storage/status")
async def storage_status():
    try:
        client = get_blob_client()
        list(client.list_containers(max_results=1))
        return {"status": "connected", "containers_accessible": True}
    except Exception as exc:
        logger.error("Storage health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})


@app.on_event("startup")
async def startup():
    logger.info("%s v%s starting up", APP_NAME, VERSION)
    logger.info("Environment: %s", os.getenv("ENVIRONMENT", "unknown"))


@app.on_event("shutdown")
async def shutdown():
    logger.info("%s shutting down", APP_NAME)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
