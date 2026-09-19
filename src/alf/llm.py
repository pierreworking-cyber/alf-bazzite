"""
Local language-model interface for ALF.

This module provides the boundary between ALF and the local Ollama
service. It sends prompts to the configured model, builds answer
requests using ALF's personality and supplied evidence, evaluates
research candidates, and checks model availability.

The language model is treated as an interpreter of prompts and evidence;
it is not treated as an independent source of trusted knowledge.
"""

import json
from urllib.request import Request, urlopen

from .personality import ALF_PERSONALITY

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MODEL = "qwen3:14b"


def generate(prompt):
    """
    Send a prompt to ALF's configured local language model.

    This is the low-level Ollama interface used by the higher-level
    functions in this module.

    Args:
        prompt: The complete prompt to send to the model.

    Returns:
        The text response returned by the language model.
    """
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")

    request = Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=60) as response:
        result = json.load(response)

    return result["response"]


def ask(answer_request):
    """
    Ask the local language model to produce an answer for ALF.

    The request combines the user's original question with any evidence
    supplied by ALF and selects either a concise or detailed answer style.

    Args:
        answer_request: A dictionary containing the question, evidence,
            and optional ``verbose`` flag.

    Returns:
        The language model's generated answer.
    """

    question = answer_request["question"]
    evidence = answer_request["evidence"]
    verbose = answer_request.get("verbose", False)

    if evidence:
        evidence_text = str(evidence)
    else:
        evidence_text = "No evidence was available."

    if evidence:
        evidence_instruction = (
            "Answer using only the supplied evidence. "
            "The supplied evidence is authoritative for this answer. "
            "Do not fill gaps with your own knowledge. "
            "If the evidence is insufficient, say so."
        )
    else:
        evidence_instruction = (
            "No external evidence was supplied. "
            "This is an ordinary knowledge or explanatory question, so "
            "you may answer using your general language-model knowledge. "
            "Do not pretend that this knowledge has been externally verified."
        )

    if verbose:
        answer_style = (
            "Give a detailed, well-developed answer. "
            "Provide useful context and explanation rather than "
            "a brief response."
        )
    else:
        answer_style = (
            "Give a concise but useful answer. "
            "Do not add unnecessary detail."
        )

    prompt = f"""
{ALF_PERSONALITY}

You are answering the user's question as the voice of ALF.

Evidence supplied by ALF:

{evidence_text}

Evidence handling:

{evidence_instruction}

User's question:

{question}

Answer style:

{answer_style}
"""

    return generate(prompt)


def evaluate_research(question, candidates):
    """
    Evaluate whether supplied research is relevant to a question.

    The local language model examines the supplied research candidates
    and identifies which candidates genuinely support answering the
    question. The model is instructed not to treat superficial word
    overlap as evidence of relevance.

    Args:
        question: The question the research should answer.
        candidates: Research candidates containing ``title`` and ``text``.

    Returns:
        A dictionary containing the relevance decision, relevant
        candidate numbers, and a brief explanation.

    Raises:
        ValueError: If the language model does not return valid JSON.
    """

    research_text = "\n\n".join(
        (
            f"Candidate {index + 1}\n"
            f"Title: {candidate['title']}\n"
            f"URL: {candidate['url']}\n"
            f"Domain: {candidate['domain']}\n"
            f"Evidence: {candidate['text']}"
        )
        for index, candidate in enumerate(candidates)
    )

    prompt = f"""
You are evaluating web research for ALF.

The user has asked a factual question. The numbered candidates below
were returned by a web search.

Determine whether any candidate contains information that can actually
support an answer to the question.

A candidate is relevant only if its content provides evidence about the
specific subject, claim, person, event, object, date, or relationship
asked about.

Do not consider a candidate relevant merely because:
- it contains similar words;
- it discusses a related subject;
- its title sounds promising;
- it could lead to an answer if combined with your own knowledge.

Do not use your own knowledge to fill gaps in the candidates.

If one or more candidates genuinely support an answer, return those
candidate numbers.

If none supports an answer, return an empty candidates list.

Return JSON only:

{{
    "relevant": true,
    "candidates": [1],
    "reason": "brief explanation"
}}

or:

{{
    "relevant": false,
    "candidates": [],
    "reason": "brief explanation"
}}

User's question:
{question}

Web research candidates:

{research_text}
"""

    response = generate(prompt).strip()

    if response.startswith("```json") and response.endswith("```"):
        response = response[7:-3].strip()

    try:
        evaluation = json.loads(response)
    except (json.JSONDecodeError, TypeError, KeyError) as error:
        raise ValueError("Invalid research evaluation response") from error

    return {
        "relevant": evaluation.get("relevant", False),
        "candidates": evaluation.get("candidates", []),
        "reason": evaluation.get("reason", ""),
    }


def check_ollama():
    """
    Check availability of the Ollama service and configured model.

    The service is queried for its installed models. A successful
    connection does not by itself mean ALF can use the configured model;
    both service availability and model availability are reported.

    Returns:
        A dictionary containing service availability, model availability,
        the configured model name, and any connection error.
    """

    request = Request(OLLAMA_TAGS_URL)

    try:
        with urlopen(request, timeout=2) as response:
            data = json.load(response)

    except Exception as error:
        return {
            "available": False,
            "model_available": False,
            "model": OLLAMA_MODEL,
            "error": str(error),
        }

    models = [
        model.get("name")
        for model in data.get("models", [])
    ]

    return {
        "available": True,
        "model_available": OLLAMA_MODEL in models,
        "model": OLLAMA_MODEL,
        "error": None,
    }
