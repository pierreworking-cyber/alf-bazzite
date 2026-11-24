
"""
Decide whether an ALF answer requires a quality assessment.

This module uses deterministic rules. It does not make language-model
calls or decide whether a user's request should be fulfilled.
"""

from .routes import Route


# These phrases indicate tasks where an incorrect or incomplete answer
# could materially mislead the user.
ASSESSMENT_TRIGGERS = (
    "how do i ",
    "how can i ",
    "how should i ",
    "how would i ",
    "give me the commands",
    "terminal commands",
    "write a script",
    "write a python script",
    "write code",
    "debug ",
    "debugging ",
    "troubleshoot",
    "troubleshooting",
    "diagnose ",
    "configure ",
    "configuration",
    "install ",
    "uninstall ",
    "replace ",
    "delete ",
    "remove ",
    "migrate ",
    "compare ",
    "advantages and disadvantages",
    "pros and cons",
    "explain how ",
    "won't boot",
    "what are the risks",
    "partition",
    "review this",
    "find any errors",
)


def should_assess(question: str, route: Route) -> bool:
    """
    Decide whether the answer should undergo quality assessment.

    Evidence-based routes are always assessed. Ordinary LLM questions
    are assessed when their wording indicates a substantial technical,
    practical or analytical task. DECLINE requires no assessment.
    """

    if route in {
        Route.SYSTEM,
        Route.MEMORY,
        Route.RESEARCH,
    }:
        return True

    if route == Route.DECLINE:
        return False

    normalised_question = " ".join(question.lower().split())

    return any(
        trigger in normalised_question
        for trigger in ASSESSMENT_TRIGGERS
    )

