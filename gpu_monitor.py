"""
GPU memory monitoring utilities
"""

import subprocess
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_gpu_memory_info() -> Dict[str, any]:
    """
    Get GPU memory usage via nvidia-smi
    Returns dict with memory info or empty dict if nvidia-smi unavailable
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {}
        
        # Parse output: "memory_used, memory_total, gpu_util"
        parts = result.stdout.strip().split(', ')
        if len(parts) >= 3:
            memory_used_mb = int(parts[0])
            memory_total_mb = int(parts[1])
            gpu_util = int(parts[2])
            
            return {
                "memory_used_mb": memory_used_mb,
                "memory_total_mb": memory_total_mb,
                "memory_used_gb": round(memory_used_mb / 1024, 2),
                "memory_total_gb": round(memory_total_mb / 1024, 2),
                "memory_used_percent": round((memory_used_mb / memory_total_mb) * 100, 1),
                "gpu_utilization_percent": gpu_util,
                "memory_available_mb": memory_total_mb - memory_used_mb,
                "memory_available_gb": round((memory_total_mb - memory_used_mb) / 1024, 2),
            }
    except FileNotFoundError:
        logger.debug("nvidia-smi not found, GPU monitoring unavailable")
        return {}
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timeout")
        return {}
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return {}
    
    return {}


def check_vram_pressure(threshold_percent: float = 90.0) -> bool:
    """
    Check if GPU VRAM usage is above threshold
    """
    gpu_info = get_gpu_memory_info()
    if not gpu_info:
        return False
    
    return gpu_info.get("memory_used_percent", 0) >= threshold_percent
