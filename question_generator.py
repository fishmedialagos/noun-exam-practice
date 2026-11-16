"""
Automated Course Mock Exam Generator for NOUN E-Exam Platform.

Analyzes parsed NOUN course material modules and study units, extracting
comprehensive high-yield question items (MCQs, cloze fill-ins, concept matching)
scaled according to course credit units:
- Minimum 70 questions for 2-unit courses
- Up to 100 questions for 3-unit courses
"""

import os
import re
import json
import random

def generate_mock_exam_questions(modules, course_code, course_title, target_count=70):
    """
    Generate balanced, high-yield exam questions from course modules and units.
    
    Includes:
    - Multiple Choice Questions (cloze and definition statements with contextual distractors)
    - Study section and topic concept classification MCQs
    - Key terminology and principle fill-in-the-gap questions
    - Verified syllabus fact assessment questions
    """
    if not modules:
        return []
        
    all_topics = []
    candidates = []
    
    # Filter out exercise instructions, TMA prompts, and reading directions
    noise_pat = re.compile(
        r'(?i)\b(self-assessment|exercise|tma\b|activity|fig\b|table\b|tutor-marked|turn to|tick|choose from|fill in|'
        r'in this unit|in this module|dear student|you are welcome|we have seen|look at|see above|see below|'
        r'let us consider|as mentioned|as stated|as we discussed|now read|study the following|copyright|all rights reserved)\b'
    )
    
    for m in modules:
        m_label = (m.get('label') or '').strip()
        for u in m.get('units') or []:
            u_label = (u.get('label') or '').strip()
            u_title = (u.get('title') or '').strip()
            u_title = re.sub(r'[\.·•]{2,}.*$', '', u_title).strip()
            body = u.get('body') or ''
            
            # Decimal sub-topics (e.g. 3.1, 3.2, 1.0)
            dec_matches = list(re.finditer(r'(?im)^(?:\s*)((?:[1-9]\d?\.\d+(?:\.\d+)?)\s*[:\-–—.]?\s+[A-Za-z][^\n]{2,80})', body))
            for idx, dm in enumerate(dec_matches):
                heading = re.sub(r'\s+', ' ', dm.group(1)).strip()
                topic_title = re.sub(r'^[0-9.]+\s*[:\-–—.]?\s*', '', heading).strip()
                topic_title = re.sub(r'[\.\:\-\–—]+$', '', topic_title).strip()
                
                if not topic_title or re.search(r'(?i)\b(introduction|conclusion|summary|tutor-marked|reference|objective)\b', topic_title):
                    continue
                if re.search(r'[_…\.]{2,}', topic_title):
                    continue
                if len(topic_title) > 60:
                    topic_title = topic_title[:57] + '...'
                    
                if topic_title not in all_topics and len(topic_title) >= 4:
                    all_topics.append(topic_title)
                    
                next_pos = dec_matches[idx+1].start() if idx+1 < len(dec_matches) else len(body)
                seg = body[dm.end():next_pos]
                s_list = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', seg))
                for s in s_list:
                    s = re.sub(r'^\s*[\(\[0-9a-zA-Z\.\-]+\)\s*', '', s.strip()).strip()
                    if 45 <= len(s) <= 200:
                        if not noise_pat.search(s) and not re.search(r'[_…\.]{2,}', s):
                            candidates.append({
                                'module': m_label,
                                'unit_label': u_label,
                                'unit_title': u_title,
                                'topic': topic_title,
                                'sentence': s
                            })

    # If decimal headings were sparse, fallback to scanning unit sentences directly
    if len(candidates) < target_count:
        for m in modules:
            m_label = (m.get('label') or '').strip()
            for u in m.get('units') or []:
                u_label = (u.get('label') or '').strip()
                u_title = (u.get('title') or '').strip()
                body = u.get('body') or ''
                s_list = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', body))
                for s in s_list:
                    s = re.sub(r'^\s*[\(\[0-9a-zA-Z\.\-]+\)\s*', '', s.strip()).strip()
                    if 45 <= len(s) <= 200:
                        if not noise_pat.search(s) and not re.search(r'[_…\.]{2,}', s):
                            candidates.append({
                                'module': m_label,
                                'unit_label': u_label,
                                'unit_title': u_title,
                                'topic': u_title or 'General Concept',
                                'sentence': s
                            })

    random.seed(42 + len(course_code))
    random.shuffle(candidates)
    
    # Collect vocabulary pool across candidates for realistic same-domain distractors
    all_vocab = set()
    for c in candidates:
        for w in c['sentence'].split():
            clean_w = w.strip('.,;:()[]"\'')
            if len(clean_w) >= 5 and clean_w.isalpha():
                all_vocab.add(clean_w.capitalize())
    vocab_list = list(all_vocab)
    
    questions = []
    q_seen = set()
    
    for item in candidates:
        if len(questions) >= target_count:
            break
            
        topic = item['topic']
        u_label = item['unit_label']
        u_title = item['unit_title'] or course_title
        s = item['sentence']
        
        sig = re.sub(r'[^a-z0-9]', '', s.lower())
        if sig in q_seen:
            continue
        q_seen.add(sig)
        
        words = [w.strip('.,;:()[]"\'') for w in s.split()]
        key_words = [w for w in words if len(w) >= 5 and w.isalpha() and w.lower() not in (
            'student', 'because', 'through', 'between', 'before', 'should', 'during',
            'another', 'without', 'always', 'number', 'system', 'different', 'learning',
            'following', 'according', 'therefore', 'towards', 'already', 'however', 'course',
            'material', 'people', 'cannot', 'called', 'rather', 'taking', 'giving', 'having',
            'which', 'where', 'there', 'their', 'these', 'those', 'under', 'while'
        )]
        
        # 1. Topic Concept Classification MCQ (every 4th question)
        if len(questions) % 4 == 0 and len(all_topics) >= 4:
            distractors = [t for t in all_topics if t.lower() != topic.lower()]
            if len(distractors) >= 3:
                chosen_dist = random.sample(distractors, 3)
                opts = [topic] + chosen_dist
                random.shuffle(opts)
                correct_letter = chr(65 + opts.index(topic))
                
                q_text = f"Which study section discusses the following statement? \"{s}\""
                questions.append({
                    'question_text': q_text,
                    'question_type': 'mcq',
                    'option_a': opts[0],
                    'option_b': opts[1],
                    'option_c': opts[2],
                    'option_d': opts[3],
                    'correct_answer': correct_letter,
                    'explanation': f"Derived from {u_label}: {u_title}, Section '{topic}'."
                })
                continue
                
        # 2. Fill-in-the-blank question (every 3rd question)
        if len(questions) % 3 == 0 and key_words:
            target_word = key_words[0]
            pattern = re.compile(rf'\b{re.escape(target_word)}\b', re.IGNORECASE)
            masked_s = pattern.sub('__________', s, count=1)
            if '__________' in masked_s:
                questions.append({
                    'question_text': f"Complete the following statement: \"{masked_s}\"",
                    'question_type': 'fill',
                    'option_a': None,
                    'option_b': None,
                    'option_c': None,
                    'option_d': None,
                    'correct_answer': target_word.lower(),
                    'explanation': f"Official courseware reference from {u_label} ({topic}): \"{s}\""
                })
                continue

        # 3. Standard 4-Option MCQ Cloze
        if key_words:
            target_word = key_words[0].capitalize()
            pattern = re.compile(rf'\b{re.escape(key_words[0])}\b', re.IGNORECASE)
            masked_s = pattern.sub('__________', s, count=1)
            
            # Select 3 distractors with similar length from vocab_list
            dist_pool = [w for w in vocab_list if w.lower() != target_word.lower() and abs(len(w) - len(target_word)) <= 4]
            if len(dist_pool) < 3:
                dist_pool = [w for w in vocab_list if w.lower() != target_word.lower()]
            if len(dist_pool) < 3:
                dist_pool = ['Knowledge', 'Comprehension', 'Communication', 'Application', 'Structure']
                
            chosen_dist = random.sample(dist_pool, 3)
            opts = [target_word] + chosen_dist
            random.shuffle(opts)
            correct_letter = chr(65 + opts.index(target_word))
            
            questions.append({
                'question_text': f"Complete the following statement: \"{masked_s}\"",
                'question_type': 'mcq',
                'option_a': opts[0],
                'option_b': opts[1],
                'option_c': opts[2],
                'option_d': opts[3],
                'correct_answer': correct_letter,
                'explanation': f"From {u_label}: {u_title} ({topic}): \"{s}\""
            })
        else:
            # 4. Factual True / False
            questions.append({
                'question_text': f"True or False: \"{s}\"",
                'question_type': 'mcq',
                'option_a': 'True',
                'option_b': 'False',
                'option_c': '',
                'option_d': '',
                'correct_answer': 'A',
                'explanation': f"Verified syllabus fact from {u_label}: {u_title} ({topic})."
            })

    return questions


def professional_paper_prompt(source, topic_title=''):
    """Turn a material statement into an exam-style theory prompt."""
    source = re.sub(r'\s+', ' ', source or '').strip()
    source = re.sub(r'^\d+(?:\.\d+){0,3}\s+(?:summary|introduction|conclusion|objectives?)\s*', '', source, flags=re.I)
    lower = source.lower()
    subject = ''
    for pattern in [
        r'\b(?:is|are)\s+(?:classified|divided|grouped|categorized)',
        r'\b(?:is|are)\s+(?:defined|known|regarded)',
        r'\b(?:is|are)\s+(?:the study|a form|an area|a branch|a process)',
        r'\b(?:refers to|means|consists of|comprises|includes|involves)',
    ]:
        match = re.search(pattern, source, flags=re.I)
        if match:
            candidate = re.sub(r'^(?:the|a|an)\s+', '', source[:match.start()].strip(' ,:;-'), flags=re.I)
            if 1 <= len(candidate.split()) <= 12:
                subject = candidate
                break
    topic = subject or re.sub(r'^(?:unit\s*\d+[\s:.-]*)', '', topic_title or '', flags=re.I).strip(' .:-')
    if not topic or re.search(r'(?i)^(?:summary|introduction|conclusion|unit\s*\d+)$', topic):
        return ''
    if any(word in lower for word in ('classified', 'divided', 'grouped', 'categorized')):
            return f"Discuss the classification of {topic}. State and explain the main bases or categories used."
    if any(word in lower for word in ('steps', 'stages', 'process', 'procedure', 'phases')):
        return f"Describe the major steps or stages involved in {topic}. Explain the importance of each stage."
    if any(word in lower for word in ('purpose', 'aim', 'objective', 'function', 'importance', 'role')):
        return f"State and explain the purpose, functions, or importance of {topic}."
    if any(word in lower for word in ('defined as', 'refers to', 'means', 'is known as', 'is the study of', 'is a branch of')):
        return f"Define {topic} and explain its meaning, scope, and relevance to the course."
    if 'following:' in lower or 'such as' in lower or 'include' in lower:
        return f"Discuss {topic}. Identify and explain the major elements or factors involved."
        return f"Discuss {topic}. Explain its key characteristics, major elements, and relevance to the course."


def _assessment_blocks(modules):
    """Yield likely assessment sections, retaining line breaks from PDF extraction."""
    heading = re.compile(
        r'(?i)\b(?:tutor[- ]marked\s+assignment|tma|self[- ]assessment|'
        r'self[- ]test|review\s+questions?|revision\s+questions?|'
        r'end[- ]of[- ]unit\s+(?:exercise|questions?)|practice\s+questions?)\b'
    )
    stop = re.compile(
        r'(?i)^\s*(?:summary|conclusion|references?|further\s+reading|'
        r'learning\s+objectives?|module\s+\d+|unit\s+\d+|'
        r'(?:tutor[- ]marked\s+assignment|tma|self[- ]assessment|'
        r'review\s+questions?|revision\s+questions?))\b'
    )
    for module in modules or []:
        for unit in module.get('units') or []:
            title = (unit.get('title') or module.get('title') or '').strip()
            lines = (unit.get('body') or '').replace('\r', '').split('\n')
            content_lines = []
            active = False
            block = []
            for raw in lines:
                line = re.sub(r'\s+', ' ', raw).strip()
                if not line:
                    if active:
                        block.append('')
                    continue
                if heading.search(line):
                    if active and block:
                        yield title, block, '\n'.join(content_lines)
                    active = True
                    block = []
                    continue
                if active and stop.match(line) and not re.match(r'(?i)^\s*(?:question|q)\b', line):
                    if block:
                        yield title, block, '\n'.join(content_lines)
                    active = False
                    block = []
                    continue
                if active:
                    block.append(line)
                else:
                    content_lines.append(line)
            if active and block:
                yield title, block, '\n'.join(content_lines)


def _parse_assessment_questions(lines):
    """Parse numbered essay-style prompts and join wrapped PDF lines."""
    starts = re.compile(r'^\s*(\d{1,2}(?:\s*[a-z])?|[a-z])\s*[\.)\-:]\s+(.*)$', re.I)
    items = []
    current = None
    for line in lines:
        line = re.sub(r'\s+', ' ', line).strip(' -•')
        if not line:
            continue
        match = starts.match(line)
        if match:
            if current:
                items.append(current)
            current = [match.group(2).strip()]
        elif current:
            current.append(line)
    if current:
        items.append(current)
    return [' '.join(item).strip() for item in items]


def _assessment_keywords(text):
    stop = {
        'which', 'what', 'where', 'when', 'whose', 'would', 'could', 'should',
        'explain', 'discuss', 'describe', 'state', 'define', 'identify',
        'outline', 'account', 'course', 'material', 'following', 'briefly',
        'using', 'with', 'from', 'this', 'that', 'their', 'there', 'about'
    }
    words = re.findall(r"[A-Za-z][A-Za-z-]{4,}", text)
    result = []
    for word in words:
        if word.lower() not in stop and word.lower() not in {x.lower() for x in result}:
            result.append(word)
        if len(result) >= 8:
            break
    return result


def _content_keywords(text, prompt):
    """Return answer-key terms from the unit discussion, not from the question itself."""
    prompt_words = {w.lower() for w in _assessment_keywords(prompt)}
    stop = {
        'which', 'what', 'where', 'when', 'whose', 'would', 'could', 'should',
        'course', 'material', 'student', 'students', 'unit', 'module', 'lesson',
        'there', 'their', 'these', 'those', 'because', 'through', 'about',
        'chapter', 'following', 'discussion', 'important', 'different',
    }
    words = re.findall(r"[A-Za-z][A-Za-z-]{5,}", text or '')
    result = []
    for word in words:
        low = word.lower()
        if low in stop or low in prompt_words or low in {x.lower() for x in result}:
            continue
        result.append(word)
        if len(result) >= 10:
            break
    return result


def _material_answer_guide(context, prompt):
    """Select a short, transparent answer guide from the preceding unit discussion."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', context or '')) if s.strip()]
    if not sentences:
        return 'Refer to the relevant discussion in the official course material and address every part of the question.'
    prompt_terms = set(_assessment_keywords(prompt))
    scored = []
    for index, sentence in enumerate(sentences):
        words = set(_assessment_keywords(sentence))
        overlap = len({w.lower() for w in words} & {w.lower() for w in prompt_terms})
        scored.append((overlap, index, sentence))
    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:3]
    selected = sorted(selected, key=lambda item: item[1])
    guide = ' '.join(item[2] for item in selected if item[0] > 0)
    if not guide:
        guide = ' '.join(sentences[:3])
    return guide[:1600].strip()


def _extract_tma_questions_from_text(text, unit_title=''):
    """Extract only written assessment prompts printed in the course material."""
    if not text or len(text) < 40:
        return []

    heading = re.compile(
        r'(?i)\b(?:tutor[- ]?marked\s+assignment(?:s)?|tma\s*\d*|'
        r'self[- ]?assessment(?:\s+(?:exercise|questions?|test))?|'
        r'review\s+questions?|revision\s+questions?|'
        r'end[- ]of[- ]unit\s+(?:exercise|questions?)|'
        r'assignment\s+questions?)\b'
    )
    stop = re.compile(
        r'(?i)^\s*(?:summary|conclusion|references?(?:/further\s+reading)?|'
        r'further\s+reading|module\s+\d+|unit\s+\d+|'
        r'\d+\.0\s+(?:introduction|objectives?|main\s+content|summary|'
        r'conclusion|references?|further\s+reading))\b'
    )
    lines = (text or '').replace('\r', '').split('\n')
    blocks = []
    active = False
    block = []
    for raw_line in lines:
        line = re.sub(r'\s+', ' ', raw_line).strip()
        if not line:
            if active:
                block.append('')
            continue
        if heading.search(line):
            if active and block:
                blocks.append(block)
            active = True
            block = []
            continue
        if active and stop.match(line):
            if block:
                blocks.append(block)
            active = False
            block = []
            continue
        if active:
            block.append(line)
    if active and block:
        blocks.append(block)

    # Numbered prompt at the beginning of a line; supports Arabic and Roman numbering.
    start = re.compile(
        r'^\s*(?:question\s*)?(?:\d{1,2}|[ivxlcdm]+)\s*[\.)\-:]\s+(.*)$', re.I
    )
    questions = []
    seen = set()
    for block in blocks:
        current = None
        items = []
        for line in block:
            match = start.match(line)
            if match:
                if current:
                    items.append(current)
                current = [match.group(1).strip()]
            elif current:
                # A PDF often places ordinary prose immediately after the last
                # assessment item. Do not attach that prose to the question once
                # the item already ends with terminal punctuation.
                if (current[-1].rstrip().endswith(('.', '?', ':')) and
                        re.match(r'^[A-Z]', line) and
                        not re.match(r'(?i)^(?:and|or|to|of|which|that|this|these|the following)\b', line)):
                    items.append(current)
                    current = None
                else:
                    current.append(line)
        if current:
            items.append(current)

        for parts in items:
            prompt = re.sub(r'\s+', ' ', ' '.join(parts)).strip(' .-–—')
            if not (18 <= len(prompt) <= 700):
                continue
            if re.match(r'(?i)^(?:answer|attempt|submit|write|note|instruction)\b', prompt) and len(prompt) < 100:
                continue
            if re.search(r'(?i)\b(?:choose the correct|select the correct|multiple[- ]choice|tick|fill in the blank)\b', prompt):
                continue
            if not re.search(
                r'(?i)\b(?:define|discuss|describe|explain|state|list|outline|'
                r'differentiate|compare|distinguish|what\s+is|what\s+are|why|how|'
                r'mention|identify|analyse|analyze|evaluate|assess|write\s+(?:short|brief|notes?)|'
                r'give\s+(?:an?\s+)?account|critically)\b', prompt
            ):
                continue
            if re.search(r'(?i)\b(?:copyright|all rights reserved|dear student|turn to page)\b', prompt):
                continue
            signature = re.sub(r'[^a-z0-9]', '', prompt.lower())
            if signature in seen:
                continue
            seen.add(signature)
            display = prompt if prompt.endswith(('?', '.', ':')) else prompt + '.'
            words = re.findall(r'[A-Za-z][A-Za-z-]{4,}', prompt)
            stop_words = {
                'which', 'where', 'there', 'their', 'these', 'those', 'because',
                'should', 'about', 'course', 'material', 'following', 'question',
                'questions', 'answer', 'write', 'briefly', 'discuss', 'explain',
                'describe', 'define', 'state', 'list'
            }
            keywords = []
            for word in words:
                if word.lower() not in stop_words and word.lower() not in {x.lower() for x in keywords}:
                    keywords.append(word)
                if len(keywords) >= 8:
                    break
            questions.append({
                'question_text': display,
                'question_type': 'essay',
                'correct_answer': 'Use the relevant discussion in the official course material and answer every part of the question.',
                'answer_keywords': keywords,
                'marks': 10 if len(display) > 80 or re.search(r'(?i)\b(discuss|critically|analyse|evaluate)\b', display) else 5,
                'explanation': 'Official assessment question extracted from the course material' + (f' ({unit_title})' if unit_title else '') + '.',
                'source': 'tma'
            })
    return questions


def generate_paper_exam_questions(modules, course_code, course_title, target_count=10, variant_seed=0):
    """Create 300L+ paper practice exclusively from official assessment prompts.

    No question is invented from ordinary explanatory prose. If the material does
    not contain enough usable assessment questions, the caller must refuse to
    publish the paper set instead of filling the gap with synthetic wording.
    """
    questions = []
    seen = set()
    for module in modules or []:
        units = module.get('units') or []
        for unit in units:
            unit_title = (unit.get('title') or module.get('title') or course_title or '').strip()
            for question in _extract_tma_questions_from_text(unit.get('body') or '', unit_title):
                signature = re.sub(r'[^a-z0-9]', '', question['question_text'].lower())
                if signature not in seen:
                    seen.add(signature)
                    questions.append(question)
        # Some PDFs store assessment text in the module body instead of a unit.
        if not units and module.get('body'):
            for question in _extract_tma_questions_from_text(module.get('body'), module.get('title') or course_title):
                signature = re.sub(r'[^a-z0-9]', '', question['question_text'].lower())
                if signature not in seen:
                    seen.add(signature)
                    questions.append(question)

    if variant_seed and questions:
        rng = random.Random(911 + len(course_code or '') + int(variant_seed) * 97)
        rng.shuffle(questions)
    return questions[:target_count]
