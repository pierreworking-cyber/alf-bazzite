"""
Introspection and health checks for ALF.

This module inspects ALF's loaded modules, command catalogue, command
handlers, and local language-model service. It reports structural or
service problems as health-check results rather than raising them as
exceptions.
"""

import importlib
import pkgutil

import alf

from .llm import check_ollama

REQUIRED_COMMAND_FIELDS = [
    "id",
    "help",
    "usage",
]


def discover_modules():
    """
    Discover and import the modules contained in the ALF package.

    Modules that fail to import are recorded with their error rather
    than preventing the remaining modules from being inspected.

    Returns:
        A list describing each discovered module and any import error.
    """

    modules = []

    for module_info in pkgutil.iter_modules(alf.__path__):
        module_name = f"alf.{module_info.name}"

        try:
            module = importlib.import_module(module_name)

        except Exception as exc:
            modules.append(
                {
                    "name": module_name,
                    "module": None,
                    "error": str(exc),
                }
            )
            continue

        modules.append(
            {
                "name": module_name,
                "module": module,
                "error": None,
            }
        )

    return modules


def check_modules(modules):
    """
    Check whether discovered ALF modules loaded successfully.

    Modules are also classified according to whether they advertise a
    ``get_capability()`` function.

    Args:
        modules: The module records returned by ``discover_modules()``.

    Returns:
        A health-check result containing the advertising, non-reporting,
        and failed modules.
    """

    advertising_modules = []
    non_reporting_modules = []
    failed_modules = []

    for discovered in modules:
        module_name = discovered["name"]
        module = discovered["module"]

        if module is None:
            failed_modules.append(
                {
                    "module": module_name,
                    "error": discovered["error"],
                }
            )
            continue

        if hasattr(module, "get_capability"):
            advertising_modules.append(module_name)
        else:
            non_reporting_modules.append(module_name)

    return {
        "name": "Modules",
        "healthy": len(failed_modules) == 0,
        "details": {
            "advertising_modules": advertising_modules,
            "non_reporting_modules": non_reporting_modules,
            "failed_modules": failed_modules,
        },
    }


def check_command_integrity(modules):
    """
    Check the command catalogue and handlers for consistency.

    Verifies that catalogue entries contain their required fields, have
    corresponding handlers, and have unique command IDs. It also checks
    for handlers that have no catalogue entry.

    Args:
        modules: The module records returned by ``discover_modules()``.

    Returns:
        A health-check result containing any command-integrity warnings.
    """

    warnings = []
    command_ids = set()

    commands_module = next(
        (
            discovered["module"]
            for discovered in modules
            if discovered["name"] == "alf.commands"
        ),
        None,
    )

    if commands_module is None:
        return {
            "name": "Commands",
            "healthy": False,
            "details": {
                "warnings": [
                    {
                        "message": "Commands module could not be loaded",
                    }
                ],
            },
        }

    catalogue = commands_module.commands
    handlers = commands_module.command_handlers
    required_fields = REQUIRED_COMMAND_FIELDS

    for name, command in catalogue.items():
        for field in required_fields:
            if field not in command:
                warnings.append(
                    {
                        "command": name,
                        "message": f"Command has no {field}",
                    }
                )

        if name not in handlers:
            warnings.append(
                {
                    "command": name,
                    "message": "Command has no handler",
                }
            )

        command_id = command.get("id")

        if not command_id:
            warnings.append(
                {
                    "command": name,
                    "message": "Command has no id",
                }
            )
            continue

        if command_id in command_ids:
            warnings.append(
                {
                    "command": name,
                    "message": f"Duplicate command id: {command_id}",
                }
            )
            continue

        command_ids.add(command_id)

    for name in handlers:
        if name not in catalogue:
            warnings.append(
                {
                    "command": name,
                    "message": "Handler has no catalogue entry",
                }
            )

    return {
        "name": "Commands",
        "healthy": len(warnings) == 0,
        "details": {
            "warnings": warnings,
        },
    }


def check_llm_service():
    """
    Check the local language-model service used by ALF.

    Checks both whether the Ollama service is available and whether the
    configured model is available to it.

    Returns:
        A health-check result describing service and model availability.
    """

    status = check_ollama()

    if not status["available"]:
        return {
            "name": "Ollama",
            "healthy": False,
            "details": {
                "service_available": False,
                "model": status["model"],
                "model_available": False,
                "error": status["error"],
            },
        }

    return {
        "name": "Ollama",
        "healthy": status["model_available"],
        "details": {
            "service_available": True,
            "model": status["model"],
            "model_available": status["model_available"],
            "error": status["error"],
        },
    }


def get_health_report():
    """
    Run all ALF health checks and combine their results.

    Returns:
        A report containing the overall health status and the individual
        results from each health check.
    """

    modules = discover_modules()

    checks = [
        check_modules(modules),
        check_command_integrity(modules),
        check_llm_service(),
    ]

    return {
        "healthy": all(check["healthy"] for check in checks),
        "checks": checks,
    }
