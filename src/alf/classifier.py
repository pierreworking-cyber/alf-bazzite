
"""
Classify questions for ALF's answer router.

The classifier selects the information source needed to answer a
question. It does not decide whether a user should be given knowledge
or infer the user's motivation.
"""

import re
from . import llm
from .routes import Route


EXAMPLES = [
    # Actual computer information
    ("What operating system am I running?", Route.SYSTEM),
    ("What GPU is installed in this computer?", Route.SYSTEM),
    ("How much RAM does this machine have?", Route.SYSTEM),
    (
        "What operating system am I running, and how do I replace it?",
        Route.SYSTEM,
    ),

    # Previous conversations and stored memories
    ("What did we decide about SearXNG?", Route.MEMORY),
    ("What did I ask you to remember about ALF?", Route.MEMORY),
    ("What have we previously decided about this project?", Route.MEMORY),

    # External or current facts
    ("What is the latest version of Python?", Route.RESEARCH),
    ("Who is the current Prime Minister of the UK?", Route.RESEARCH),
    ("What is the weather forecast for tomorrow?", Route.RESEARCH),
    ("Who wrote The Moon's a Balloon?", Route.RESEARCH),
    ("When was Python first released?", Route.RESEARCH),

    # Questions and tasks answerable locally
    ("What does pytest -q mean?", Route.LLM),
    ("Explain the difference between a list and a tuple.", Route.LLM),
    ("How do I delete my operating system?", Route.LLM),
    ("Write a short thank-you note.", Route.LLM),
    ("Translate hello into French.", Route.LLM),
    ("Reply with exactly one word: OK", Route.LLM),

    # Capabilities ALF does not possess
    ("Can you make me a cup of tea?", Route.DECLINE),
    ("Can you physically repair my computer?", Route.DECLINE),
]

TEMPORAL_PATTERNS = (
    r"\bcurrent(?:ly)?\b",
    r"\blatest\b",
    r"\bnewest\b",
    r"\brecent(?:ly)?\b",
    r"\btoday\b",
    r"\btonight\b",
    r"\byesterday\b",
    r"\btomorrow\b",
    r"\bright now\b",
    r"\bas of now\b",
    r"\bat present\b",
    r"\bup[\s-]+to[\s-]+date\b",
    r"\bthis (?:morning|afternoon|evening|week|month|year)\b",
    r"\bin the last \d+ (?:hours?|days?|weeks?|months?|years?)\b",
)


def has_temporal_sensitivity(question):
    """Return whether a question explicitly requires time-sensitive information."""
    return any(
        re.search(pattern, question, re.IGNORECASE)
        for pattern in TEMPORAL_PATTERNS
    )


def classify(question):
    """
    Select the route best suited to answering a user's question.

    Args:
        question: The user's question or request.

    Returns:
        A Route value.

    Raises:
        ValueError: If the language model returns an unknown route.
    """

    examples = "\n".join(
        f"{text} -> {route.value}"
        for text, route in EXAMPLES
    )

    prompt = f"""
Choose exactly one route for the user's request:

system
memory
research
llm
decline

ROUTES

SYSTEM:
The answer requires information about this actual computer,
such as its operating system, hardware or configuration.

MEMORY:
The answer requires recalling previous conversations or stored
information about the user or their projects.

RESEARCH:
The answer requires current facts or verification from external
sources.

LLM:
The request can be answered using local knowledge and reasoning.
Includes explanations, technical instructions, calculations,
writing, translation and ordinary conversation.

DECLINE:
The request requires ALF to physically perform an action or use
a capability it does not possess.

RULES

1. Classify by the information needed to answer, not by keywords.
2. Mentioning a computer or operating system does not automatically
   mean SYSTEM.
3. General technical instructions belong to LLM, even when they
   describe destructive operations. ALF provides knowledge; the
   user decides what to do with it.
4. Use SYSTEM when answering requires facts about this actual machine.
   This takes precedence over LLM when a request combines both.
5. Use MEMORY when answering requires previous conversations.
6. Use RESEARCH when answering requires external or current facts.
7. Use DECLINE only when ALF genuinely lacks the capability required.
8. Do not infer harmful motivation or refuse ordinary requests
   merely because of their subject matter.

EXAMPLES

{examples}

Return only the route name.

USER'S REQUEST:
{question}
"""

    result = llm.generate(
        prompt,
        think=False,
        options={"num_predict": 16},
    ).strip().lower()

    try:
        route = Route(result)
    except ValueError as error:
        raise ValueError(
            f"Invalid routing classification: {result}"
        ) from error

    if (
        has_temporal_sensitivity(question)
        and route not in (Route.SYSTEM, Route.MEMORY)
    ):
        return Route.RESEARCH

    return route
