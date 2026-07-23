from typing import Any, Dict, List, Optional
import httpx


class StateClient:
    """
    Diting In-Memory State HTTP Server 客户端。
    具备 5.0 秒超时拦截与 Fail-Fast 友好异常捕获。
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 5.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url, timeout=self.timeout, transport=self.transport
        )

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            with self._get_client() as client:
                resp = client.request(method, path, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise RuntimeError(
                f"Diting State Server not reachable at {self.base_url}. Please start state server first."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"State Server API Error: {e.response.status_code} - {e.response.text}"
            ) from e

    def get_metrics(
        self,
        session_id: str,
        metric: str,
        start_tick: int = 0,
        end_tick: int = 100,
        real_now: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params = {
            "session_id": session_id,
            "metric": metric,
            "start_tick": start_tick,
            "end_tick": end_tick,
        }
        if real_now:
            params["real_now"] = real_now
        return self._request("GET", "/api/v1/metrics", params=params)

    def get_logs(
        self,
        session_id: str,
        service: str,
        level: str = "ERROR",
        real_now: Optional[str] = None,
    ) -> List[str]:
        params = {"session_id": session_id, "service": service, "level": level}
        if real_now:
            params["real_now"] = real_now
        return self._request("GET", "/api/v1/logs", params=params)

    def get_traces(
        self, session_id: str, real_now: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"session_id": session_id}
        if real_now:
            params["real_now"] = real_now
        return self._request("GET", "/api/v1/traces", params=params)

    def get_alerts(
        self, session_id: str, status: str = "firing", real_now: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"session_id": session_id, "status": status}
        if real_now:
            params["real_now"] = real_now
        return self._request("GET", "/api/v1/alerts", params=params)

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("DELETE", "/api/v1/session", params={"session_id": session_id})
