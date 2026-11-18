"""Hybrid NOUN mock-exam generator: AI generation plus deterministic QA."""
import json
import logging
import os
import re
import difflib
import requests

LOGGER = logging.getLogger(__name__)
NOISE_RE = re.compile(r"(?i)\b(self-assessment|tutor[- ]marked|\bTMA\b|copyright|all rights reserved|table of contents|learning objectives?|activity)\b")


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n-–—•")


def _source_units(modules):
    units = []
    for module in modules or []:
        module_label = _clean(module.get("label")) or "Course material"
        for unit in module.get("units") or []:
            title = _clean(unit.get("title")) or _clean(unit.get("label")) or "Study unit"
            paragraphs = []
            for paragraph in re.split(r"\n+", str(unit.get("body") or "")):
                paragraph = _clean(paragraph)
                if len(paragraph) >= 45 and not NOISE_RE.search(paragraph) and not re.fullmatch(r"[\d.\s]+", paragraph):
                    paragraphs.append(paragraph)
            text = "\n".join(paragraphs)
            if len(text) >= 250:
                units.append({"module": module_label, "unit": _clean(unit.get("label")) or title, "title": title, "text": text[:14000]})
    return units


def _api_settings():
    """Resolve the configured provider; OpenAI is preferred when both keys exist.

    QUESTION_AI_PROVIDER can explicitly be set to 'openai' or 'groq'.
    If it is omitted, OpenAI is selected first, then Groq.
    """
    provider = (os.environ.get("QUESTION_AI_PROVIDER") or "auto").strip().lower()
    if provider not in {"auto", "openai", "groq"}:
        LOGGER.warning("Unsupported QUESTION_AI_PROVIDER=%r; using automatic provider selection.", provider)
        provider = "auto"

    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        return ("https://api.openai.com/v1/chat/completions", key,
                os.environ.get("OPENAI_MODEL", "gpt-4o-mini")) if key else None
    if provider == "groq":
        key = os.environ.get("GROQ_API_KEY")
        return ("https://api.groq.com/openai/v1/chat/completions", key,
                os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")) if key else None

    if os.environ.get("OPENAI_API_KEY"):
        return ("https://api.openai.com/v1/chat/completions", os.environ["OPENAI_API_KEY"],
                os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    if os.environ.get("GROQ_API_KEY"):
        return ("https://api.groq.com/openai/v1/chat/completions", os.environ["GROQ_API_KEY"],
                os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    return None


def _call_question_ai(source, course_code, course_title, count):
    settings = _api_settings()
    if not settings:
        LOGGER.warning("Mock exam generation requires OPENAI_API_KEY or GROQ_API_KEY; refusing low-quality fallback.")
        return []
    url, key, model = settings
    prompt = f'''Create {count} rigorous undergraduate examination questions for National Open University of Nigeria (NOUN).
Course: {course_code} — {course_title}
Source unit: {source['module']} / {source['unit']} / {source['title']}
Use ONLY the following source for facts and correct answers:
{source['text']}

QUALITY REQUIREMENTS:
- Assess important concepts, definitions, principles, classifications, theories, functions, relationships, comparisons, causes/effects, processes and reasonable applications actually covered in this source.
- Test understanding, not location of quotations or random words removed from sentences.
- Use clear, complete, formal academic English appropriate for undergraduate examinations.
- Do not invent facts, scholars, dates, examples or terminology absent from the source.
- Avoid vague stems, trivial recall, trick wording, immature wording, grammatical clues and duplicate testing of the same fact.
- Produce a balanced mix: approximately half MCQ and half fill-in-the-gap.

MCQ: Provide a self-contained stem and four plausible, relevant, distinct options. Exactly one answer must be defensible. Distractors should be credible misconceptions or related subject concepts, not random words. Options should be parallel in grammar and specificity. correct_answer must be the exact correct option text.

FILL: Use one blank for a meaningful technical term or concept explicitly supported by the source. Do not blank articles, prepositions or generic verbs. Provide the exact expected answer.

Return ONLY JSON: {{"questions":[{{"question_type":"mcq","question_text":"...","option_a":"...","option_b":"...","option_c":"...","option_d":"...","correct_answer":"exact option text","explanation":"Brief explanation grounded in this source."}},{{"question_type":"fill","question_text":"... __________ ...","option_a":null,"option_b":null,"option_c":null,"option_d":null,"correct_answer":"...","explanation":"Brief explanation grounded in this source."}}]}}
No markdown. Generate only questions the source supports; do not pad with weak items.'''
    payload = {"model": model, "messages": [
        {"role": "system", "content": "You are a careful university assessment setter. Source fidelity and academic quality take priority over quantity. Return valid JSON only."},
        {"role": "user", "content": prompt}], "temperature": 0.25,
        "max_tokens": min(7000, max(1800, count * 115)), "response_format": {"type": "json_object"}}
    response = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=(8, 75))
    if response.status_code != 200:
        LOGGER.warning("Mock question AI HTTP %s (%s): %s",
                       response.status_code, model, response.text[:500])
        return []
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    parsed = json.loads(content)
    return parsed.get("questions", []) if isinstance(parsed, dict) else parsed if isinstance(parsed, list) else []


def _validate(raw, source, seen):
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("question_type") or "").strip().lower()
    stem, answer, explanation = _clean(raw.get("question_text")), _clean(raw.get("correct_answer")), _clean(raw.get("explanation"))
    source_text = source["text"].casefold()
    if kind not in {"mcq", "fill"} or not 35 <= len(stem) <= 650 or not answer or len(answer) > 180 or len(explanation) < 20:
        return None
    if not any(term in explanation.casefold() for term in ("source", "material", "concept", "principle", "definition", "section", source["title"].casefold(), source["unit"].casefold())):
        return None
    if re.search(r"(?i)\b(which page|which section contains|where in the material|according to the quotation)\b", stem):
        return None
    if len(re.findall(r"_{3,}", stem)) > 1:
        return None
    signature = re.sub(r"[^a-z0-9]+", " ", stem.casefold()).strip()
    if signature in seen or any(difflib.SequenceMatcher(None, signature, old).ratio() >= 0.88 for old in seen):
        return None
    result = {"question_text": stem, "question_type": kind, "option_a": None, "option_b": None, "option_c": None, "option_d": None, "correct_answer": answer, "explanation": explanation}
    if kind == "mcq":
        options = [_clean(raw.get("option_" + x)) for x in "abcd"]
        if any(not x or len(x) > 220 for x in options) or len({x.casefold() for x in options}) != 4:
            return None
        matches = [i for i, option in enumerate(options) if option.casefold() == answer.casefold()]
        if len(matches) != 1 or any(x.casefold() in {"all of the above", "none of the above", "true", "false"} for x in options):
            return None
        result.update({"option_" + letter: option for letter, option in zip("abcd", options)})
        answer_terms = [word for word in re.findall(r"[a-z]{5,}", answer.casefold())]
        if answer_terms and not any(word in source_text for word in answer_terms):
            return None
        result["correct_answer"] = "ABCD"[matches[0]]
    else:
        if not re.search(r"_{3,}", stem) or len(answer.split()) > 6 or len(answer) < 3:
            return None
        if answer.casefold() not in source_text and answer.casefold().rstrip("s") not in source_text:
            return None
        result["correct_answer"] = answer.casefold()
    terms = [w for w in re.findall(r"[a-z]{5,}", stem.casefold()) if w not in {"which", "what", "where", "when", "whose", "about", "should", "would", "could", "following", "statement", "course", "material", "concept"}]
    if terms and not any(term in source_text for term in terms):
        return None
    result["explanation"] = f"{explanation} Source: {source['module']}, {source['unit']} — {source['title']}."
    seen.add(signature)
    return result


def generate_mock_exam_questions(modules, course_code, course_title, target_count=70):
    """Generate AI questions and retain only those passing deterministic QA.

    It intentionally returns fewer than target_count if quality or source coverage
    is insufficient. The application must not publish an underfilled exam.
    """
    units = _source_units(modules or [])
    if not units:
        return []
    target_count = max(1, min(int(target_count), 150))
    questions, seen = [], set()
    mcq_limit = (target_count + 1) // 2
    fill_limit = target_count // 2
    rounds_needed = max(4, (target_count + (len(units) * 10) - 1) // (len(units) * 10) + 1)
    for _round in range(rounds_needed):
        if len(questions) >= target_count:
            break
        for source in units:
            remaining = target_count - len(questions)
            if remaining <= 0:
                break
            try:
                proposed = _call_question_ai(source, course_code, course_title, min(10, remaining + 3))
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                LOGGER.warning("Question generation failed for %s/%s: %s", course_code, source["unit"], exc)
                proposed = []
            except Exception:
                LOGGER.exception("Unexpected question-generation error for %s", course_code)
                proposed = []
            for item in proposed:
                clean = _validate(item, source, seen)
                if clean:
                    current_type_count = sum(q["question_type"] == clean["question_type"] for q in questions)
                    type_limit = mcq_limit if clean["question_type"] == "mcq" else fill_limit
                    if current_type_count >= type_limit:
                        continue
                    questions.append(clean)
                    if len(questions) >= target_count:
                        break
    mcqs = [q for q in questions if q["question_type"] == "mcq"]
    fills = [q for q in questions if q["question_type"] == "fill"]
    mixed = []
    while mcqs or fills:
        if mcqs:
            mixed.append(mcqs.pop(0))
        if fills:
            mixed.append(fills.pop(0))
    return mixed[:target_count]
