
from alf import system


def test_read_system_interface_reads_permitted_interface(monkeypatch):
    monkeypatch.setattr(
        system,
        "SYSTEM_INTERFACES",
        {"test": "/proc/test"},
    )

    monkeypatch.setattr(
        "builtins.open",
        lambda path: FakeFile("first: one\nsecond: two\n"),
    )

    assert system.read_system_interface("test") == (
        "first: one\nsecond: two\n"
    )


def test_read_system_interface_rejects_unknown_interface():
    assert system.read_system_interface("not_permitted") is None


def test_read_system_interface_handles_missing_file(monkeypatch):
    monkeypatch.setattr(
        system,
        "SYSTEM_INTERFACES",
        {"test": "/does/not/exist"},
    )

    def fail_open(path):
        raise OSError("file not found")

    monkeypatch.setattr("builtins.open", fail_open)

    assert system.read_system_interface("test") is None


def test_read_system_value_reads_named_value(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: (
            "MemTotal:       32768000 kB\n"
            "MemAvailable:   16384000 kB\n"
        ),
    )

    assert system.read_system_value("proc_meminfo", "MemTotal") == (
        "32768000 kB"
    )

    assert system.read_system_value("proc_meminfo", "MemAvailable") == (
        "16384000 kB"
    )


def test_read_system_value_returns_none_for_unknown_key(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: "MemTotal: 32768000 kB\n",
    )

    assert system.read_system_value("proc_meminfo", "SwapTotal") is None


def test_read_system_value_returns_none_when_interface_unavailable(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: None,
    )

    assert system.read_system_value("proc_meminfo", "MemTotal") is None


def test_read_system_field_reads_positional_field(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: "123.45 678.90\n",
    )

    assert system.read_system_field("proc_uptime", 0) == "123.45"
    assert system.read_system_field("proc_uptime", 1) == "678.90"


def test_read_system_field_returns_none_for_missing_field(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: "123.45\n",
    )

    assert system.read_system_field("proc_uptime", 1) is None


def test_get_cpu_information_reads_cpu_model(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: (
            "processor\t: 0\n"
            "vendor_id\t: AuthenticAMD\n"
            "model name\t: AMD Ryzen 5 7600 6-Core Processor\n"
            "cpu MHz\t: 4500.000\n"
        ),
    )

    assert system.get_cpu_information() == (
        "AMD Ryzen 5 7600 6-Core Processor"
    )


def test_get_cpu_information_returns_none_without_model(monkeypatch):
    monkeypatch.setattr(
        system,
        "read_system_interface",
        lambda name: (
            "processor\t: 0\n"
            "vendor_id\t: AuthenticAMD\n"
        ),
    )

    assert system.get_cpu_information() is None


def test_get_disk_information_returns_usage(monkeypatch):
    usage = system.shutil.disk_usage

    monkeypatch.setattr(
        system.shutil,
        "disk_usage",
        lambda path: usage(path)._replace(
            total=1_000_000_000_000,
            used=500_000_000_000,
            free=500_000_000_000,
        ),
    )

    assert system.get_disk_information("/") == {
        "path": "/",
        "total": 1_000_000_000_000,
        "used": 500_000_000_000,
        "free": 500_000_000_000,
    }


def test_get_disk_information_handles_failure(monkeypatch):
    def fail_disk_usage(path):
        raise OSError("cannot read filesystem")

    monkeypatch.setattr(
        system.shutil,
        "disk_usage",
        fail_disk_usage,
    )

    assert system.get_disk_information("/") is None


def test_get_system_information_combines_available_information(monkeypatch):
    monkeypatch.setattr(system.platform, "system", lambda: "Linux")
    monkeypatch.setattr(system.platform, "node", lambda: "alf-machine")
    monkeypatch.setattr(system.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(system.platform, "python_version", lambda: "3.14.6")

    monkeypatch.setattr(
        system,
        "read_system_field",
        lambda interface, index: "12345.67",
    )

    def fake_value(interface, key):
        values = {
            ("proc_meminfo", "MemTotal"): "32768000 kB",
            ("proc_meminfo", "MemAvailable"): "16384000 kB",
        }
        return values.get((interface, key))

    monkeypatch.setattr(system, "read_system_value", fake_value)
    monkeypatch.setattr(
        system,
        "get_cpu_information",
        lambda: "AMD Ryzen 5 7600 6-Core Processor",
    )
    monkeypatch.setattr(
        system,
        "get_gpu_information",
        lambda: "AMD/ATI AMD Radeon RX 9070 XT",
    )
    monkeypatch.setattr(
        system,
        "get_disk_information",
        lambda path: {
            "path": path,
            "total": 1_000_000,
            "used": 500_000,
            "free": 500_000,
        },
    )

    assert system.get_system_information() == {
        "operating_system": "Linux",
        "hostname": "alf-machine",
        "architecture": "x86_64",
        "python_version": "3.14.6",
        "uptime": "12345.67",
        "total_memory": "32768000 kB",
        "available_memory": "16384000 kB",
        "cpu": "AMD Ryzen 5 7600 6-Core Processor",
        "gpu": "AMD/ATI AMD Radeon RX 9070 XT",
        "disk": {
            "path": "/",
            "total": 1_000_000,
            "used": 500_000,
            "free": 500_000,
        },
    }


def test_get_system_information_survives_unavailable_interrogations(
    monkeypatch,
):
    monkeypatch.setattr(system.platform, "system", lambda: "Linux")
    monkeypatch.setattr(system.platform, "node", lambda: "alf-machine")
    monkeypatch.setattr(system.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(system.platform, "python_version", lambda: "3.14.6")

    monkeypatch.setattr(
        system,
        "read_system_field",
        lambda interface, index: None,
    )
    monkeypatch.setattr(
        system,
        "read_system_value",
        lambda interface, key: None,
    )
    monkeypatch.setattr(
        system,
        "get_cpu_information",
        lambda: None,
    )
    monkeypatch.setattr(
        system,
        "get_gpu_information",
        lambda: None,
    )
    monkeypatch.setattr(
        system,
        "get_disk_information",
        lambda path: None,
    )

    assert system.get_system_information() == {
        "operating_system": "Linux",
        "hostname": "alf-machine",
        "architecture": "x86_64",
        "python_version": "3.14.6",
        "uptime": None,
        "total_memory": None,
        "available_memory": None,
        "cpu": None,
        "gpu": None,
        "disk": None,
    }


def test_get_capability_describes_system_awareness():
    result = system.get_capability()

    assert result["id"] == "system"
    assert result["name"] == "System awareness"
    assert "proc_meminfo" in result["interfaces"]
    assert "proc_uptime" in result["interfaces"]


class FakeFile:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def read(self):
        return self.content
