"""
Identity and self-description for ALF.

This module loads ALF's persistent identity information, adds the
installed package version, and combines identity data with discovered
capabilities for the ``about`` interface.
"""

import tomllib
from importlib.metadata import version as package_version

from .capabilities import discover_capabilities
from .paths import get_data_directory


def get_identity():
    """
    Load ALF's persistent identity information.

    If no user identity exists yet, bootstrap the packaged default
    identity into ALF's data directory. An existing user identity is
    never overwritten.

    Returns:
        A dictionary containing ALF's identity information and current
        installed package version.
    """
    identity_file = get_data_directory() / "identity.toml"

    if not identity_file.exists():
        identity_file.parent.mkdir(parents=True, exist_ok=True)

        from importlib.resources import files

        default_identity = files("alf").joinpath("identity.toml")
        identity_file.write_bytes(default_identity.read_bytes())

    with open(identity_file, "rb") as file:
        identity = tomllib.load(file)

    identity["version"] = package_version("alf")

    return identity


def get_about_information():
    """
    Build the structured information presented by ALF's ``about`` command.

    Combines persistent identity information with currently discovered
    capabilities and any capability-discovery warnings.

    Returns:
        A dictionary containing identity, capabilities, warnings, and
        declared limitations.
    """
    identity = get_identity()
    report = discover_capabilities()

    return {
        "identity": identity,
        "capabilities": report["capabilities"],
        "warnings": report["warnings"],
        "limitations": identity["limitations"],
    }
