"""Weaviate Client Manager."""

import asyncio
import time

import weaviate
from weaviate.classes.init import AdditionalConfig, Auth, Timeout
from weaviate.client import WeaviateClient
from weaviate.exceptions import WeaviateConnectionError, WeaviateGRPCUnavailableError

from config.settings import settings
from src.utils.logger import get_logger

from .config import GRPC_TIMEOUT, HTTP_TIMEOUT, STARTUP_TIMEOUT

logger = get_logger(__name__)


class WeaviateClientManager:
    """Manages the Weaviate client lifecycle (Singleton pattern)."""

    _client: WeaviateClient | None = None

    @classmethod
    def get_client(cls) -> WeaviateClient:
        """Get or create Weaviate client instance."""
        if cls._client is not None:
            if cls._client.is_connected():
                return cls._client

            logger.warning("Weaviate client disconnected, reconnecting...")
            try:
                cls._client.connect()
                return cls._client
            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
                ConnectionError,
                WeaviateGRPCUnavailableError,
            ) as ex:
                logger.error("[WEAVIATE_RECONNECT_FAIL] Reconnection failed: %s", ex)
                # Fall through to re-creation
                cls._client = None

        # Create new client
        return cls._create_client()

    @classmethod
    def _create_client(cls) -> WeaviateClient:
        """Create and connect a new Weaviate client."""
        logger.info(
            f"Connecting to Weaviate at {settings.weaviate_url} (gRPC: {settings.weaviate_grpc_url})..."
        )

        # Parse URLs
        # settings.weaviate_url is like "http://weaviate:8080"
        url_str = str(settings.weaviate_url)
        http_host = (
            url_str.replace("http://", "")
            .replace("https://", "")
            .rsplit(":", maxsplit=1)[0]
        )
        http_port = int(url_str.rsplit(":", maxsplit=1)[-1])

        # settings.weaviate_grpc_url is like "weaviate:50051"
        grpc_str = str(settings.weaviate_grpc_url)
        grpc_host = grpc_str.rsplit(":", maxsplit=1)[0]
        grpc_port = int(grpc_str.rsplit(":", maxsplit=1)[-1])

        # Auth config
        auth_config = None
        if settings.weaviate_api_key:
            auth_config = Auth.api_key(settings.weaviate_api_key)
            logger.info("Using API key authentication for Weaviate")

        # Connect
        try:
            client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=False,  # Internal docker network is usually http
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                grpc_secure=False,
                auth_credentials=auth_config,
                additional_config=AdditionalConfig(
                    timeout=Timeout(
                        init=STARTUP_TIMEOUT, query=HTTP_TIMEOUT, insert=GRPC_TIMEOUT
                    )
                ),
                skip_init_checks=False,
            )

            cls._client = client
            logger.info("Successfully connected to Weaviate")
            return client

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            ConnectionError,
            WeaviateConnectionError,
            WeaviateGRPCUnavailableError,
        ) as ex:
            # Log the error summary only — the full traceback is too noisy for a
            # known-offline scenario and gets printed by the Weaviate SDK internally.
            logger.error(
                "[WEAVIATE_CONNECT_FAIL] Could not connect to Weaviate: %s", ex
            )
            raise ConnectionError(f"Could not connect to Weaviate: {ex}") from ex

    @classmethod
    async def ensure_ready(cls, timeout: int = STARTUP_TIMEOUT) -> bool:
        """Wait for Weaviate to be ready (async — FIX-011)."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                client = cls.get_client()
                if client.is_ready():
                    return True
            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
                ConnectionError,
                WeaviateConnectionError,
            ):
                pass

            logger.debug("Waiting for Weaviate to be ready...")
            await asyncio.sleep(
                2
            )  # FIX-011: was time.sleep(2) — was blocking event loop

        logger.error("[WEAVIATE_TIMEOUT] Readiness check timed out after %ds", timeout)
        return False

    @classmethod
    def close(cls):
        """Close Weaviate connection."""
        if cls._client:
            try:
                cls._client.close()
                logger.info("Weaviate connection closed")
            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
                ConnectionError,
            ) as ex:
                logger.error(
                    "[WEAVIATE_CLOSE_FAIL] Error closing Weaviate connection: %s", ex
                )
            finally:
                cls._client = None
