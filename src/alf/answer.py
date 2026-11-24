"""
Answer preparation for ALF.

This module prepares the structured request passed to the language-model
layer. It keeps answer preparation separate from the process that
obtains and evaluates research evidence.
"""

from .llm import ask

def prepare_answer(
    original_question,
    research_question,
    evidence,
    verbose=False,
    research_judgement=None,
    research_unavailable=False,
    evidence_type="none",
    assessment_correction=None,
):

    """
    Prepare an answer request and send it to the language-model layer.

    The original user question, the question used for research, any
    selected evidence, and the requested response style are combined
    into the structured request expected by ``ask()``.

    Args:
        original_question: The question as entered by the user.
        research_question: The question used to obtain research evidence.
        evidence: Research evidence selected for use in the answer.
        verbose: Whether to request a more detailed response.
        research_judgement: The conclusion reached by the evidence review.
        research_unavailable: Whether reliable live research evidence is unavailable.

    Returns:
        The answer produced by the language-model layer.
    """

    answer_request = {
        "question": original_question,
        "research_question": research_question,
        "evidence": evidence,
        "verbose": verbose,
        "evidence_type": evidence_type,
        "research_judgement": research_judgement,
        "research_unavailable": research_unavailable,
        "assessment_correction": assessment_correction,
    }

    return ask(answer_request)
