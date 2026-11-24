"""
Question-processing engine for ALF.

This module coordinates the end-to-end process of answering a user
question. It routes the question, interprets it when research is
required, searches for evidence, evaluates that evidence, and passes
relevant evidence to the answer-generation layer.

Research questions are interpreted and searched on the web. If no reliable
research is found, the engine returns an explicit failure rather than asking
the language model to guess.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .answer import prepare_answer
from .interpretation import interpret_question
from .memory import find_relevant_memories
from .research import (
    evaluate_evidence,
    research_web,
    select_evidence,
)
from .router import route
from .routes import Route
from .system import get_system_information
from .assessment import should_assess
from .llm import evaluate_answer

@dataclass
class QuestionResult:
    """Result produced by the question-processing engine.

    Attributes:
        answer: The final answer presented to the user.
        source: The source used to support the answer, or ``None`` when
            no reliable evidence was found.
        research_question: The interpreted question used for research,
            or ``None`` when research was not required.
        news_items: The stored news items supporting a news answer, or
            ``None`` when the answer is not news-backed.
    """

    answer: str
    source: str | None
    research_question: str | None
    news_items: list | None = None


def answer_question(
    original_question: str,
    verbose: bool = False,
    progress: Callable[[str], None] | None = None,
) -> QuestionResult:
    """Process a user question and return the resulting answer.

    Questions are first routed to determine whether they can be answered
    directly by the local language model or require research. Research
    questions are interpreted and searched on the web.

    Only evidence judged relevant by the research evaluator is passed to
    the answer-generation layer. If no reliable evidence is found, the
    function returns a failure result rather than guessing.

    Args:
        original_question: The question as entered by the user.
        verbose: Whether to request a more detailed answer.
        progress: Optional callback used to report significant stages of
            question processing.

    Returns:
        A ``QuestionResult`` containing the answer, its source, and the
        research question used during the process.
    """

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    report("Routing question…")
    selected_route = route(original_question)

    if selected_route == Route.LLM:
        report("Asking local language model…")

        answer = prepare_answer(
            original_question,
            original_question,
            [],
            verbose=verbose,
        )

        if should_assess(original_question, selected_route):
            report("Checking answer quality…")

            evaluation = evaluate_answer(
                question=original_question,
                answer=answer,
                route=selected_route.name,
                evidence=[],
            )

            if evaluation["verdict"] == "ACCEPT":
                report("Answer accepted.")

            elif evaluation["verdict"] == "REVISE":
                report("Revising answer...")

                answer = prepare_answer(
                    original_question,
                    original_question,
                    [],
                    verbose=verbose,
                    assessment_correction=evaluation["correction"],
                )

                report("Checking revised answer…")

                second_evaluation = evaluate_answer(
                    question=original_question,
                    answer=answer,
                    route=selected_route.name,
                    evidence=[],
                )

                if second_evaluation["verdict"] == "ACCEPT":
                    report("Revised answer accepted.")

                elif second_evaluation["verdict"] == "REVISE":
                    report("The revised answer still has an unresolved issue.")

                    reason = (
                        second_evaluation.get("correction", "").strip()
                        or "; ".join(second_evaluation.get("issues", []))
                        or second_evaluation.get("reason", "")
                        or "The revised answer may still contain an error."
                    )

                    answer = (
                        f"{answer}\n\n"
                        "ALF could not establish that the revised answer "
                        "is reliable. The final assessment identified: "
                        f"{reason}"
                    )

                elif second_evaluation["verdict"] == "RESEARCH":
                    report("Revised answer needs independent verification.")

                    correction = (
                        second_evaluation.get("correction", "").strip()
                        or "; ".join(second_evaluation.get("issues", []))
                        or second_evaluation.get("reason", "")
                        or "Verify the material facts in the revised answer."
                    )

                    research_query = (
                        f"{original_question}\n\n"
                        "Additional point requiring verification: "
                        f"{correction}"
                    )

                    return research_answer(
                        original_question,
                        research_query,
                        verbose,
                        report,
                        fallback_answer=answer,
                    )

                elif second_evaluation["verdict"] == "UNRESOLVED":
                    report("Revised answer reliability could not be established.")

                    reason = second_evaluation.get("reason") or (
                        "There is insufficient information to establish "
                        "whether the revised answer is reliable."
                    )

                    answer = (
                        f"{answer}\n\n"
                        "ALF could not establish that this revised answer "
                        f"is reliable. {reason}"
                    )

            elif evaluation["verdict"] == "RESEARCH":
                report("Answer needs independent verification.")

                correction = (
                    evaluation["correction"].strip()
                    or "; ".join(evaluation["issues"])
                    or evaluation["reason"]
                    or "Verify the material facts in the original answer."
                )

                research_query = (
                    f"{original_question}\n\n"
                    "Additional point requiring verification: "
                    f"{correction}"
                )

                return research_answer(
                    original_question,
                    research_query,
                    verbose,
                    report,
                    fallback_answer=answer,
                )

            elif evaluation["verdict"] == "UNRESOLVED":
                report("Answer reliability could not be established.")

                reason = evaluation.get("reason") or (
                    "There is insufficient information to establish "
                    "whether the answer is reliable."
                )

                answer = (
                    f"{answer}\n\n"
                    "ALF could not establish that this answer is reliable. "
                    f"{reason}"
                )

        return QuestionResult(
            answer=answer,
            source="llm",
            research_question=None,
        )

    if selected_route == Route.SYSTEM:
        report("Reading system information…")

        system_information = get_system_information()

        report("Asking local language model…")

        answer = prepare_answer(
            original_question,
            original_question,
            [system_information],
            verbose=verbose,
            evidence_type="system",
        )

        return QuestionResult(
            answer=answer,
            source="system",
            research_question=None,
        )

    if selected_route == Route.MEMORY:
        report("Searching memory…")

        memories = find_relevant_memories(original_question)

        if memories:
            report("Asking local language model…")

            answer = prepare_answer(
                original_question,
                original_question,
                memories,
                verbose=verbose,
                evidence_type="memory",
            )

            return QuestionResult(
                answer=answer,
                source="memory",
                research_question=None,
            )

        return QuestionResult(
            answer=(
                "I couldn't find any relevant memories about that. "
                "I don't want to guess."
            ),
            source=None,
            research_question=None,
        )

    if selected_route == Route.DECLINE:
        return QuestionResult(
            answer="I can't help with that.",
            source=None,
            research_question=None,
        )

    return research_answer(
        original_question,
        original_question,
        verbose,
        report,
        fallback_answer=None,
    )


def research_answer(
    original_question,
    research_query,
    verbose,
    report,
    fallback_answer=None,
):
    """Research a question and generate an answer from accepted evidence."""

    def answer_without_research(research_question, judgement):
        """Answer without claiming that live research verified the result."""

        report("Answering without verified web evidence…")

        answer = prepare_answer(
            original_question,
            research_question,
            [],
            verbose=verbose,
            research_judgement=judgement,
            research_unavailable=True,
        )

        return QuestionResult(
            answer=answer,
            source="llm",
            research_question=research_question,
        )

    research_question = research_query
    fallback_judgement = None

    try:
        report("Interpreting question…")
        research_question = interpret_question(research_query)

        report("Researching the web…")
        web_candidates = research_web(research_question)

        if not web_candidates:
            fallback_judgement = (
                "Live research returned no usable evidence."
            )
        else:
            report("Evaluating web evidence…")
            web_evaluation = evaluate_evidence(
                research_question,
                web_candidates,
            )

            if not isinstance(web_evaluation, dict):
                raise ValueError("Invalid research evaluation")

            evaluation_answer = web_evaluation.get("answer")
            confidence = web_evaluation.get("confidence")
            supporting = web_evaluation.get("supporting_candidates")
            rejected = web_evaluation.get("rejected_candidates")
            reason = web_evaluation.get("reason")

            if (
                not isinstance(evaluation_answer, str)
                or not evaluation_answer.strip()
                or confidence not in {"high", "medium", "low"}
                or not isinstance(supporting, list)
                or not isinstance(rejected, list)
                or not isinstance(reason, str)
            ):
                raise ValueError("Incomplete research evaluation")

            research_judgement = (
                f"Best-supported answer: {evaluation_answer}\n"
                f"Confidence: {confidence}\n"
                f"Reason: {reason}"
            )

            relevant_candidates = select_evidence(
                web_candidates,
                web_evaluation,
            )

            if confidence == "low":
                fallback_judgement = (
                    "The evidence review found only low-confidence "
                    "support. No web evidence has been accepted as reliable."
                )
            elif not relevant_candidates:
                fallback_judgement = research_judgement

    except Exception:
        fallback_judgement = (
            "Live research or its evidence review failed. "
            "No web evidence has been accepted as reliable."
        )

    if fallback_judgement is not None:
        if fallback_answer is not None:
            report("Additional research could not verify the answer.")

            return QuestionResult(
                answer=(
                    f"{fallback_answer}\n\n"
                    "ALF attempted additional research, but could not "
                    "verify the information. The original answer should "
                    "therefore be treated as unverified."
                ),
                source="llm",
                research_question=research_question,
            )

        return answer_without_research(
            research_question,
            fallback_judgement,
        )

    report("Asking local language model…")

    answer = prepare_answer(
        original_question,
        research_question,
        relevant_candidates,
        verbose=verbose,
        research_judgement=research_judgement,
        evidence_type="research",
    )

    return QuestionResult(
        answer=answer,
        source="web",
        research_question=research_question,
    )

def _news_result_summary(items):
    """
    Produce a deterministic summary of matching stored news items.

    Args:
        items: The news item dictionaries returned by ``query_items``.

    Returns:
        The answer text describing how many stored news items matched
        the question's topics.
    """

    terms = []

    for item in items:
        for term in item["matched_terms"]:
            if term not in terms:
                terms.append(term)

    topic = ", ".join(terms) if terms else "your topic"

    return (
        f"Found {len(items)} stored news item"
        f"{'s' if len(items) != 1 else ''} matching {topic}."
    )
