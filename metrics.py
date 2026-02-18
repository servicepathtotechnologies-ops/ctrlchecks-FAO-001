"""
Prometheus-style metrics collection
"""

import time
from typing import Dict, List
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Thread-safe metrics collector for Prometheus format
    """
    
    def __init__(self):
        self._lock = Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()
    
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] | None = None):
        """Increment a counter metric"""
        with self._lock:
            key = self._format_key(name, labels)
            self._counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] | None = None):
        """Set a gauge metric"""
        with self._lock:
            key = self._format_key(name, labels)
            self._gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] | None = None):
        """Record a histogram value"""
        with self._lock:
            key = self._format_key(name, labels)
            self._histograms[key].append(value)
            # Keep only last 1000 values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
    
    def _format_key(self, name: str, labels: Dict[str, str] | None) -> str:
        """Format metric key with labels"""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format"""
        with self._lock:
            lines = []
            
            # Counters
            for key, value in sorted(self._counters.items()):
                lines.append(f"{key} {value}")
            
            # Gauges
            for key, value in sorted(self._gauges.items()):
                lines.append(f"{key} {value}")
            
            # Histograms (as summaries)
            for key, values in sorted(self._histograms.items()):
                if values:
                    count = len(values)
                    total = sum(values)
                    avg = total / count if count > 0 else 0
                    lines.append(f"{key}_count {count}")
                    lines.append(f"{key}_sum {total}")
                    lines.append(f"{key}_avg {avg}")
            
            # Uptime
            uptime = time.time() - self._start_time
            lines.append(f"service_uptime_seconds {uptime}")
            
            return "\n".join(lines)
    
    def get_json_metrics(self) -> Dict:
        """Get metrics as JSON"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "avg": sum(v) / len(v) if v else 0,
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                },
                "uptime_seconds": time.time() - self._start_time,
            }


# Global metrics instance
metrics = MetricsCollector()
