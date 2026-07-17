from datetime import datetime, timezone
from fastapi import FastAPI, Query
from typing import Optional, Dict
from simulator.projections.metric import MetricProjection
from simulator.projections.log import LogProjection
from simulator.projections.trace import TraceProjection
from simulator.projections.alert import AlertmanagerProjection

def create_app(metric_proj: MetricProjection, 
               log_proj: LogProjection, 
               trace_proj: TraceProjection, 
               alert_proj: AlertmanagerProjection) -> FastAPI:
    
    app = FastAPI(title="Diting In-Memory State HTTP Server")
    
    # 会话物理时间锚点缓存：session_id -> datetime
    session_anchors: Dict[str, datetime] = {}
    
    def _get_session_anchor(session_id: str, client_real_now: Optional[str]) -> datetime:
        """
        获取或锁定当前 session 的物理时间锚点。
        - 若客户端（如评测平台）显式传入 real_now，则以其为准。
        - 否则，在会话第一次被访问时锁定当前物理 Now，并在后续所有多次乱序查询中复用，防止漂移。
        """
        if client_real_now:
            # 容错处理：'+' 被解码为空格
            return datetime.fromisoformat(client_real_now.replace(" ", "+"))
            
        if session_id not in session_anchors:
            session_anchors[session_id] = datetime.now(timezone.utc)
            
        return session_anchors[session_id]
    
    @app.get("/api/v1/metrics")
    def get_metrics(session_id: str, metric: str, start_tick: int = 0, end_tick: int = 100, real_now: Optional[str] = None):
        t_now = _get_session_anchor(session_id, real_now)
        return metric_proj.query_metric(session_id, metric, start_tick, end_tick, t_now)
        
    @app.get("/api/v1/logs")
    def get_logs(session_id: str, service: str, level: str = "ERROR", real_now: Optional[str] = None):
        t_now = _get_session_anchor(session_id, real_now)
        return log_proj.query_logs(session_id, service, level, t_now)
        
    @app.get("/api/v1/traces")
    def get_traces(session_id: str, real_now: Optional[str] = None):
        t_now = _get_session_anchor(session_id, real_now)
        return trace_proj.query_traces(session_id, t_now)
        
    @app.get("/api/v1/alerts")
    def get_alerts(session_id: str, status: str = "firing", real_now: Optional[str] = None):
        t_now = _get_session_anchor(session_id, real_now)
        if status == "firing":
            return alert_proj.get_firing_alerts(session_id, t_now)
        elif status == "resolved":
            return alert_proj.get_resolved_alerts(session_id, t_now)
        return []
        
    @app.delete("/api/v1/session")
    def delete_session(session_id: str):
        # 移除时间锚点
        session_anchors.pop(session_id, None)
        
        # 零 I/O 内存清空逻辑
        if session_id in metric_proj.metrics_db:
            metric_proj.metrics_db.pop(session_id)
        if session_id in log_proj.logs_db:
            log_proj.logs_db.pop(session_id)
        if session_id in trace_proj.traces_db:
            trace_proj.traces_db.pop(session_id)
        if session_id in alert_proj.firing_alerts:
            alert_proj.firing_alerts.pop(session_id)
        if session_id in alert_proj.resolved_alerts:
            alert_proj.resolved_alerts.pop(session_id)
            
        return {"status": "cleared", "session_id": session_id}
        
    return app
