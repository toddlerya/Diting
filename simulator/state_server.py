from datetime import datetime
from fastapi import FastAPI, Query
from typing import Optional
from simulator.projections.metric import MetricProjection
from simulator.projections.log import LogProjection
from simulator.projections.trace import TraceProjection
from simulator.projections.alert import AlertmanagerProjection

def create_app(metric_proj: MetricProjection, 
               log_proj: LogProjection, 
               trace_proj: TraceProjection, 
               alert_proj: AlertmanagerProjection) -> FastAPI:
    
    app = FastAPI(title="Diting In-Memory State HTTP Server")
    
    @app.get("/api/v1/metrics")
    def get_metrics(session_id: str, metric: str, start_tick: int = 0, end_tick: int = 100):
        return metric_proj.query_metric(session_id, metric, start_tick, end_tick)
        
    @app.get("/api/v1/logs")
    def get_logs(session_id: str, service: str, level: str = "ERROR"):
        return log_proj.query_logs(session_id, service, level)
        
    @app.get("/api/v1/traces")
    def get_traces(session_id: str, real_now: Optional[str] = None):
        t_now = datetime.fromisoformat(real_now) if real_now else datetime.now()
        return trace_proj.query_traces(session_id, t_now)
        
    @app.get("/api/v1/alerts")
    def get_alerts(session_id: str, status: str = "firing"):
        if status == "firing":
            return alert_proj.get_firing_alerts(session_id)
        elif status == "resolved":
            return alert_proj.get_resolved_alerts(session_id)
        return []
        
    @app.delete("/api/v1/session")
    def delete_session(session_id: str):
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
