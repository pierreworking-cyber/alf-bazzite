"""
ALF system awareness.

Provides information about the machine ALF is running on.
"""

import platform
import shutil
import subprocess

SYSTEM_INTERFACES = {
    "proc_meminfo": "/proc/meminfo",
    "proc_uptime": "/proc/uptime",
    "proc_cpuinfo": "/proc/cpuinfo",
}


def read_system_value(interface, key):
    """Read a named value from a key/value system interface."""
    data = read_system_interface(interface)

    if data is None:
        return None

    for line in data.splitlines():
        name, separator, value = line.partition(":")

        if separator and name.strip() == key:
            return value.strip()

    return None


def read_system_interface(name):
    """Read a permitted system interface."""
    path = SYSTEM_INTERFACES.get(name)

    if path is None:
        return None

    try:
        with open(path) as file:
            return file.read()

    except OSError:
        return None


def read_system_field(interface, index):
    """Read a positional field from a system interface."""
    data = read_system_interface(interface)

    if data is None:
        return None

    fields = data.split()

    try:
        return fields[index]
    except IndexError:
        return None


def get_gpu_information():
    """Return the first graphics controller reported by lspci."""
    if shutil.which("lspci") is None:
        return None

    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if "VGA compatible controller:" in line:
            return line.split("VGA compatible controller:", 1)[1].strip()

        if "3D controller:" in line:
            return line.split("3D controller:", 1)[1].strip()

    return None


def get_cpu_information():
    """Return the CPU model reported by /proc/cpuinfo."""
    data = read_system_interface("proc_cpuinfo")

    if data is None:
        return None

    for line in data.splitlines():
        name, separator, value = line.partition(":")

        if separator and name.strip() == "model name":
            return value.strip()

    return None


def get_disk_information(path="/"):
    """Return filesystem usage information for a path."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None

    return {
        "path": path,
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
    }


def get_system_information():
    """
    Return system information as structured data.
    """

    information = {}

    information["operating_system"] = platform.system()
    information["hostname"] = platform.node()
    information["architecture"] = platform.machine()
    information["python_version"] = platform.python_version()

    information["uptime"] = read_system_field(
        "proc_uptime",
        0,
    )

    information["total_memory"] = read_system_value(
        "proc_meminfo",
        "MemTotal",
    )
    information["available_memory"] = read_system_value(
        "proc_meminfo",
        "MemAvailable",
    )

    information["cpu"] = get_cpu_information()
    information["gpu"] = get_gpu_information()
    information["disk"] = get_disk_information("/")

    return information


def get_capability():
    """
    Return system awareness capability information.
    """

    return {
        "id": "system",
        "name": "System awareness",
        "description": "Provides controlled access to permitted system interfaces",
        "interfaces": list(SYSTEM_INTERFACES),
    }
