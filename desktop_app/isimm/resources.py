import subprocess
import psutil


def resources(cpu_interval=None):
    vm = psutil.virtual_memory()
    used = total = 0
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
                "-i",
                "0",
            ],
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
        used, total = map(int, gpu.stdout.strip().split(","))
    except (ValueError, OSError, subprocess.SubprocessError):
        pass
    return dict(
        cpu=psutil.cpu_percent(interval=cpu_interval),
        available=vm.available / 2**30,
        ram=(vm.total - vm.available) / 2**30,
        ram_total=vm.total / 2**30,
        vram=used,
        vram_total=total,
        vram_free=total - used,
    )
