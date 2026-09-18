"""
Question classification for ALF's answer router.

This module uses the local language model to classify a user's question
into one of ALF's routing categories. The resulting category determines
which part of ALF is responsible for answering the question.
"""

from . import llm
from .routes import Route

EXAMPLES = [
    ("What operating system am I running?", Route.SYSTEM),
    ("What OS is this machine running?", Route.SYSTEM),
    ("What GPU is in this computer?", Route.SYSTEM),
    ("What did we decide about SearXNG?", Route.MEMORY),
    ("What did I ask you to remember about ALF?", Route.MEMORY),
    ("What have we previously decided about the project?", Route.MEMORY),
    ("What is the latest version of Python?", Route.RESEARCH),
    ("Who is the current Prime Minister of the UK?", Route.RESEARCH),
    ("What is the weather forecast for tomorrow?", Route.RESEARCH),
    ("Who wrote The Moon's a Balloon?", Route.RESEARCH),
    ("Who invented the telephone?", Route.RESEARCH),
    ("When was Python first released?", Route.RESEARCH),
    ("What does pytest -q mean?", Route.LLM),
    ("What is the difference between a list and a tuple in Python?", Route.LLM),
    ("What does a Python virtual environment do?", Route.LLM),
    ("Can ALF physically repair my computer?", Route.DECLINE),
    ("Can you make me a cup of tea?", Route.DECLINE),
    ("How do I delete my operating system?", Route.DECLINE),
    ("What operating system am I running, and how do I delete it?", Route.DECLINE),
]


def classify(question):
    """
    Classify a question into one of ALF's routing categories.

    The local language model is given the question and a set of
    representative examples, then asked to return exactly one routing
    category. The result is converted to a ``Route`` value so that the
    router can dispatch the question deterministically.

    Args:
        question: The user's question to classify.

    Returns:
        The ``Route`` corresponding to the classified question.

    Raises:
        ValueError: If the language model returns a value that is not a
            recognised routing category.
    """

    examples = "\n".join(
        f"{example_question} -> {route.value}"
        for example_question, route in EXAMPLES
    )

    prompt = f"""
Classify the user's question into exactly one of these categories:

system
memory
research
llm
decline

SYSTEM means the question requires information about this computer.

MEMORY means the question asks about something Peter and ALF previously
remembered, discussed, or decided.

RESEARCH means the question asks for a factual answer that should be
verified against an external source, including facts about people,
books, films, music, events, dates, places, or current developments.

LLM means the question is explanatory or conceptual and can be answered
without external verification.
DECLINE means ALF has no suitable capability or reliable source.

Use the examples below as guidance.

Examples:
{examples}

Return exactly one category name and nothing else.

User's question:
{question}
"""

    result = llm.generate(prompt).strip().lower()

    try:
        return Route(result)
    except ValueError as error:
        raise ValueError(f"Invalid routing classification: {result}") from error
