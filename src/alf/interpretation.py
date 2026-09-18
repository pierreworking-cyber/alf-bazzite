"""
Question interpretation for ALF.

Provides a small boundary between ALF's original user questions and
language-model reformulation for research.
"""

from .llm import generate


def interpret_question(question):
    """
    Prepare a user's question for research.

    If the question is already clear and suitable for research, it is
    returned unchanged. Otherwise, the local language model reformulates
    it into a clearer research question while preserving its meaning and
    specific terminology.

    The function does not answer the question or add new facts.

    Args:
        question: The user's original question.

    Returns:
        The original question or a reformulated version suitable for
        research.
    """

    prompt = f"""
You are preparing a user's question for a research search.

Your task is to determine whether the question is already clear and
suitable for research.

If the question is already clear and suitable for research, return it
unchanged.

If the question is ambiguous, awkward, or likely to produce poor search
results, reformulate it into a clearer question that is suitable for
research.

If the question contains an apparent spelling error or malformed
specific term, correct it when the intended term is reasonably clear.

Do not answer the question.
Do not provide an explanation.
Do not add facts that are not implied by the question.
Do not change the subject of the question.
Preserve the meaning of the user's question.
Preserve useful and specific terminology already present in the question.
Do not replace terminology merely to make the wording sound more natural.
Do not turn a question into a request for information that the original
question does not ask for.
Return only the question.

User's question:
{question}
"""

    return generate(prompt).strip()
