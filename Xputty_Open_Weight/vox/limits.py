"""Two-core CPU execution limits and honest per-process memory measurement."""

import os
import platform
import time

_CPU_MAX = 2
_MEM_MAX = 4 * 1024**3


def limit_cpu(cores=2):
    cores = int(cores)
    if not 1 <= cores <= 2:
        raise ValueError("Vox only permits 1 or 2 requested CPU cores")
    os.environ["OMP_NUM_THREADS"] = str(cores)
    os.environ["MKL_NUM_THREADS"] = str(cores)
    os.environ["OPENBLAS_NUM_THREADS"] = str(cores)
    os.environ["NUMEXPR_NUM_THREADS"] = str(cores)
    try:
        import psutil

        p = psutil.Process()
        allowed = p.cpu_affinity() if hasattr(p, "cpu_affinity") else []
        if len(allowed) > cores:
            p.cpu_affinity(allowed[:cores])
    except (ImportError, NotImplementedError, AttributeError, OSError, ValueError):
        pass
    import torch

    torch.set_num_threads(cores)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    return torch


def rss_bytes():
    try:
        import psutil

        return psutil.Process().memory_info().rss
    except ImportError:
        return 0


def memory_guard(limit_gb=4.0):
    if not (0 < float(limit_gb) <= 4):
        raise ValueError("memory limit cannot exceed 4 GB")
    rss = rss_bytes()
    if rss and rss > float(limit_gb) * 1024**3:
        raise MemoryError(f"Vox R02 RSS budget exceeded: {rss / 1024**3:.2f} GiB")
    return rss


def environment():
    import torch

    return dict(
        platform=platform.platform(),
        python=platform.python_version(),
        torch=str(torch.__version__),
        cpu_count=os.cpu_count(),
        torch_threads=torch.get_num_threads(),
        rss_bytes=rss_bytes(),
        timestamp=time.time(),
    )
