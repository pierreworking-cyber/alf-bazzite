"""
Capability discovery for ALF.

This module discovers ALF modules that advertise capabilities and
collects those capabilities into a common registry. It also validates
basic capability contracts and reports problems as warnings rather than
allowing one faulty provider to prevent discovery of the others.
"""

import importlib
import pkgutil

import alf


def get_alf_modules():
    """
    Discover and import the modules contained in the ALF package.

    Returns:
        A list of imported ALF modules.
    """

    modules = []

    for module_info in pkgutil.iter_modules(alf.__path__):
        module_name = f"alf.{module_info.name}"

        module = importlib.import_module(module_name)

        modules.append(module)

    return modules


def get_provider_modules():
    """
    Find ALF modules that advertise a capability provider.

    A provider is any ALF module exposing a ``get_capability()``
    function.

    Returns:
        A list of ALF modules that provide capabilities.
    """

    providers = []

    for module in get_alf_modules():
        if hasattr(module, "get_capability"):
            providers.append(module)

    return providers


def discover_capabilities():
    """
    Discover capabilities and validate their basic contracts.

    Each provider is asked for its capability and the capability must
    have a unique, non-empty ``id``. Problems encountered while loading
    providers or validating capabilities are collected as warnings so
    that one faulty provider does not prevent other capabilities from
    being discovered.

    Returns:
        A dictionary containing two keys:

        ``capabilities``
            The successfully discovered capabilities.

        ``warnings``
            A list of dictionaries describing providers that could not
            be included.
    """
    capabilities = []
    warnings = []
    capability_ids = set()

    for provider in get_provider_modules():
        try:
            capability = provider.get_capability()

            capability_id = capability.get("id")

            if not capability_id:
                warnings.append(
                    {
                        "module": provider.__name__,
                        "message": "Capability has no id",
                    }
                )
                continue

            if capability_id in capability_ids:
                warnings.append(
                    {
                        "module": provider.__name__,
                        "message": f"Duplicate capability id: {capability_id}",
                    }
                )
                continue

            capability_ids.add(capability_id)
            capabilities.append(capability)

        except Exception as exc:
            warnings.append(
                {
                    "module": provider.__name__,
                    "message": str(exc),
                }
            )

    return {
        "capabilities": capabilities,
        "warnings": warnings,
    }
