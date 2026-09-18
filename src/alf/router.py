"""ALF's answer-routing boundary."""

from .classifier import classify


def route(question):
    """
    Decide which ALF capability should handle a question.
    """
    return classify(question)
