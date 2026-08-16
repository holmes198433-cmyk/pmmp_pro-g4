import json
import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class AsyncNHTSAClient:
    """
    Asynchronous client for fetching vehicle recalls and technical service bulletins (TSBs/complaints)
    from NHTSA API with local disk caching.
    """

    RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVin?vin={vin}&format=json"
    TSBS_URL = "https://api.nhtsa.gov/complaints/complaintsByVin?vin={vin}&format=json"

    def __init__(self, cache_dir: str = ".cache", timeout: float = 5.0):
        self.cache_dir = cache_dir
        self.timeout = timeout
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, vin: str) -> str:
        safe_vin = "".join(c for c in vin if c.isalnum() or c in ("-", "_")).upper()
        return os.path.join(self.cache_dir, f"nhtsa_{safe_vin}.json")

    def _read_cache(self, vin: str) -> Dict[str, Any]:
        cache_file = self._get_cache_path(vin)
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read NHTSA cache for VIN {vin}: {e}")
        return {}

    def _write_cache(self, vin: str, section: str, data: Any) -> None:
        try:
            cache_file = self._get_cache_path(vin)
            cached_data = self._read_cache(vin)
            cached_data[section] = data
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cached_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write NHTSA cache for VIN {vin}: {e}")

    async def get_recalls(self, vin: str) -> Dict[str, Any]:
        """
        Fetch recalls for the given VIN asynchronously.
        Returns cached data on failure or timeout.
        """
        if not vin:
            return {}

        clean_vin = vin.strip().upper()
        url = self.RECALLS_URL.format(vin=clean_vin)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    self._write_cache(clean_vin, "recalls", data)
                    return data
                else:
                    logger.warning(
                        f"NHTSA recalls returned status {response.status_code} for VIN {clean_vin}"
                    )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning(f"NHTSA recalls request failed for VIN {clean_vin}: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error querying NHTSA recalls for VIN {clean_vin}: {exc}")

        # Fallback to local cache
        cached = self._read_cache(clean_vin)
        return cached.get("recalls", {})

    async def get_tsbs(self, vin: str) -> Dict[str, Any]:
        """
        Fetch TSBs/complaints for the given VIN asynchronously.
        Returns cached data on failure or timeout.
        """
        if not vin:
            return {}

        clean_vin = vin.strip().upper()
        url = self.TSBS_URL.format(vin=clean_vin)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    self._write_cache(clean_vin, "tsbs", data)
                    return data
                else:
                    logger.warning(
                        f"NHTSA complaints returned status {response.status_code} for VIN {clean_vin}"
                    )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning(f"NHTSA complaints request failed for VIN {clean_vin}: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error querying NHTSA complaints for VIN {clean_vin}: {exc}")

        # Fallback to local cache
        cached = self._read_cache(clean_vin)
        return cached.get("tsbs", {})
