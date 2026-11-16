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

def generate_mock_exam_questions(modules, course_code, course_title, target_count=70, variant_seed=0):
    """
    Generate balanced, high-yield exam questions from course modules and units.
    
    Includes:
    - Multiple Choice Questions (cloze and definition statements with contextual distractors)
    - Study section and topic concept classification MCQs
    - Key terminology and principle fill-in-the-gap questions
    - Verified syllabus fact assessment questions

    variant_seed: different integers produce different question orderings / sets
    so multiple students do not always see the identical paper.
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

    # Different variant_seed values produce different question orderings / selections
    random.seed(42 + len(course_code or '') + int(variant_seed or 0) * 97)
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
                
                q_text = f"Which study section discusses the following: \"{s}\"?"
                questions.append({
                    'question_text': q_text,
                    'question_type': 'mcq',
                    'option_a': opts[0],
                    'option_b': opts[1],
                    'option_c': opts[2],
                    'option_d': opts[3],
                    'correct_answer': correct_letter,
                    'explanation': f"From {u_label}: {u_title}, section '{topic}'."
                })
                continue
                
        # 2. Fill-in-the-blank question (every 3rd question)
        if len(questions) % 3 == 0 and key_words:
            target_word = key_words[0]
            pattern = re.compile(rf'\b{re.escape(target_word)}\b', re.IGNORECASE)
            masked_s = pattern.sub('__________', s, count=1)
            if '__________' in masked_s:
                questions.append({
                    'question_text': f"Complete the statement: \"{masked_s}\"",
                    'question_type': 'fill',
                    'option_a': None,
                    'option_b': None,
                    'option_c': None,
                    'option_d': None,
                    'correct_answer': target_word.lower(),
                    'explanation': f"From {u_label} ({topic}): \"{s}\""
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
                'explanation': f"From {u_label}: {u_title} ({topic})."
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
                'explanation': f"From {u_label}: {u_title} ({topic})."
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


def _extract_tma_questions_from_text(text, unit_title=''):
    """
    Extract real Tutor-Marked Assignment (TMA) and Self-Assessment questions
    from NOUN course material text. These are the official practice questions
    designed by the course writers and are the best source for paper-mode exams.
    """
    if not text or len(text) < 40:
        return []

    questions = []
    seen = set()

    # Normalise whitespace while preserving paragraph breaks enough for regex
    raw = re.sub(r'[ \t]+', ' ', text)
    raw = re.sub(r'\n{3,}', '\n\n', raw)

    # Locate TMA / Tutor-Marked Assignment / Self-Assessment Exercise blocks
    section_pat = re.compile(
        r'(?is)'
        r'(?:'
        r'(?:tutor[- ]?marked\s+assignment(?:s)?(?:\s*\(tma\s*\d*\))?)|'
        r'(?:tma\s*\d*\s*[:.\-–]?\s*(?:questions?)?)|'
        r'(?:self[- ]?assessment\s+(?:exercise|question|test)s?)|'
        r'(?:assignment\s+(?:questions?|file))'
        r')'
        r'\s*[:.\-]?\s*'
        r'(.*?)'
        r'(?='
        r'\n\s*(?:'
        r'[0-9]+\s*\.\s*0\s+(?:introduction|objectives?|main\s+content|summary|conclusion|references?|further\s+reading)|'
        r'tutor[- ]?marked\s+assignment|'
        r'self[- ]?assessment|'
        r'references?/further\s+reading|'
        r'module\s+\d+|'
        r'unit\s+\d+'
        r')'
        r'|\Z'
        r')',
        re.IGNORECASE
    )

    blocks = section_pat.findall(raw)
    if not blocks:
        # Fallback: look for short "Answer the following" style regions near TMA mentions
        for m in re.finditer(r'(?is)(?:tutor[- ]?marked\s+assignment|tma\b).{0,120}?(answer the following|attempt the following|answer all).{0,40}', raw):
            start = m.end()
            chunk = raw[start:start + 1200]
            blocks.append(chunk)

    for block in blocks:
        block = block.strip()
        if len(block) < 30:
            continue

        # Split into individual questions. Support:
        # 1. / 1) / i. / ii. / a. / (a) / Question 1
        item_pat = re.compile(
            r'(?m)^\s*(?:'
            r'(?:question\s*)?\d{1,2}[\.\)\:]|'
            r'[ivx]+\.|'
            r'[a-e][\.\)]|'
            r'\([a-e0-9ivx]+\)'
            r')\s+',
            re.IGNORECASE
        )
        parts = item_pat.split(block)
        # The first part is often the instruction ("Answer the following questions.")
        items = []
        for p in parts:
            p = re.sub(r'\s+', ' ', p).strip(' \n\t-–—')
            if not p:
                continue
            # Drop pure instructions
            if re.match(r'(?i)^(answer|attempt|submit|write|discuss\s+any|choose\s+any|note:|instruction)', p):
                if len(p) < 80:
                    continue
            # Reasonable question length
            if 15 <= len(p) <= 600:
                items.append(p)

        for qtext in items:
            # Clean residual numbering / leading junk
            qtext = re.sub(r'^(?:[0-9ivxa-e]+[\.\)\:]|\([0-9ivxa-e]+\))\s*', '', qtext, flags=re.I).strip()
            qtext = re.sub(r'\s+', ' ', qtext).strip(' .')
            if len(qtext) < 18:
                continue
            # Skip pure meta text
            if re.search(r'(?i)\b(copyright|all rights reserved|dear student|turn to page|see the end)\b', qtext):
                continue
            # Prefer questions that look like exam prompts
            if not re.search(
                r'(?i)\b(define|discuss|describe|explain|state|list|outline|differentiate|compare|distinguish|'
                r'what\s+is|what\s+are|why|how|mention|identify|analyse|analyze|evaluate|assess|'
                r'write\s+(?:short|brief|notes)|give\s+(?:an?\s+)?account|critically)\b',
                qtext
            ) and len(qtext) < 40:
                continue

            sig = re.sub(r'[^a-z0-9]', '', qtext.lower())[:120]
            if sig in seen:
                continue
            seen.add(sig)

            # Extract simple keywords for answer guidance
            words = re.findall(r'[A-Za-z][A-Za-z-]{3,}', qtext)
            stop = {'which', 'there', 'their', 'these', 'those', 'because', 'should', 'where',
                    'about', 'course', 'material', 'following', 'questions', 'answer', 'write',
                    'briefly', 'discuss', 'explain', 'describe', 'define', 'state', 'list'}
            keywords = []
            for w in words:
                if w.lower() not in stop and w.lower() not in {x.lower() for x in keywords}:
                    keywords.append(w)
                if len(keywords) >= 6:
                    break

            # Ensure it ends with a question mark or is a clear imperative
            display = qtext
            if not display.endswith(('?', '.', ':')):
                display += '.'

            questions.append({
                'question_text': display,
                'question_type': 'essay',
                'correct_answer': '',  # TMA answers are not in the material; student must write from knowledge
                'answer_keywords': keywords,
                'marks': 10 if len(display) > 80 or re.search(r'(?i)\b(discuss|critically|analyse|evaluate)\b', display) else 5,
                'explanation': f"Official Tutor-Marked Assignment question from the course material"
                               + (f" ({unit_title})" if unit_title else "") + ".",
                'source': 'tma'
            })

    return questions


def generate_paper_exam_questions(modules, course_code, course_title, target_count=10, variant_seed=0):
    """
    Build pen-and-paper (theory/essay) practice questions for 300-level and above.

    Priority order:
    1. Real Tutor-Marked Assessment (TMA) / Self-Assessment questions extracted
       from the official course material (best quality – written by course team).
    2. Professionally rephrased theory prompts derived from key statements in
       the material (fallback when TMAs are sparse).

    variant_seed: different integers produce different question orderings / sets.
    """
    tma_questions = []
    seen_sigs = set()

    # ---- Pass 1: extract authentic TMAs from every unit ----
    for module in modules or []:
        for unit in module.get('units') or []:
            unit_title = (unit.get('title') or '').strip()
            body = unit.get('body') or ''
            extracted = _extract_tma_questions_from_text(body, unit_title)
            for q in extracted:
                sig = re.sub(r'[^a-z0-9]', '', q['question_text'].lower())[:100]
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    tma_questions.append(q)

    # Also try full concatenated text in case TMAs were split across units
    if len(tma_questions) < target_count:
        full_text = '\n\n'.join(
            (u.get('body') or '')
            for m in (modules or [])
            for u in (m.get('units') or [])
        )
        extra = _extract_tma_questions_from_text(full_text, course_title or '')
        for q in extra:
            sig = re.sub(r'[^a-z0-9]', '', q['question_text'].lower())[:100]
            if sig not in seen_sigs:
                seen_sigs.add(sig)
                tma_questions.append(q)

    # Prefer a balanced set of TMAs (shuffle for variety across modules / variants)
    random.seed(911 + len(course_code or '') + int(variant_seed or 0) * 97)
    random.shuffle(tma_questions)

    questions = tma_questions[:target_count]

    # ---- Pass 2: supplement with generated professional prompts if needed ----
    if len(questions) < target_count:
        candidates, seen = [], set()

        def clean_source(text):
            text = re.sub(r'\s+', ' ', text or '').strip(' -•')
            text = re.sub(r'^\d+(?:\.\d+){0,3}\s+(?:summary|introduction|conclusion|objectives?)\s*', '', text, flags=re.I)
            text = re.sub(r'^(?:summary|introduction|conclusion)\s*[:.-]?\s*', '', text, flags=re.I)
            return text.strip(' .')

        def subject_before(text, patterns):
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.I)
                if match:
                    subject = text[:match.start()].strip(' ,:;-')
                    subject = re.sub(r'^(?:the|a|an)\s+', '', subject, flags=re.I)
                    if 1 <= len(subject.split()) <= 12:
                        return subject
            return ''

        def professional_prompt(source, topic_title):
            lower = source.lower()
            subject = subject_before(source, [
                r'\b(?:is|are)\s+(?:classified|divided|grouped|categorized)',
                r'\b(?:is|are)\s+(?:defined|known|regarded)',
                r'\b(?:is|are)\s+(?:the study|a form|an area|a branch|a process)',
                r'\b(?:refers to|means|consists of|comprises|includes|involves)',
                r'\b(?:has|have)\s+(?:the following|several|different)',
            ])
            fallback_topic = re.sub(r'^(?:unit\s*\d+[\s:.-]*)', '', topic_title or '', flags=re.I).strip(' .:-')
            if 'classified' in lower or 'divided' in lower or 'grouped' in lower or 'categorized' in lower:
                return f"Discuss the classification of {subject or 'the concept described in the course material'}. State and explain the main bases or categories used."
            if any(word in lower for word in ('steps', 'stages', 'process', 'procedure', 'phases')):
                return f"Describe the major steps or stages involved in {subject or 'the process discussed'}. Explain the importance of each stage."
            if any(word in lower for word in ('purpose', 'aim', 'objective', 'function', 'importance', 'role')):
                return f"State and explain the purpose, functions, or importance of {subject or 'the concept discussed in this unit'}."
            if any(word in lower for word in ('defined as', 'refers to', 'means', 'is known as', 'is the study of', 'is a branch of')):
                return f"Define {subject or 'the key concept discussed'} and explain its meaning, scope, and relevance to the course."
            if any(word in lower for word in ('difference', 'differentiate', 'similarities', 'distinguish')):
                return f"Differentiate the related concepts discussed in this section and state at least two important differences."
            if 'following:' in lower or 'such as' in lower or 'include' in lower:
                return f"Discuss {subject or 'the topic discussed in this section'}. Identify and explain the major elements or factors involved."
            return f"Discuss {subject or fallback_topic}. Explain its key characteristics, major elements, and relevance to the course." if (subject or fallback_topic) else ''

        for module in modules or []:
            for unit in module.get('units') or []:
                unit_title = (unit.get('title') or course_title).strip()
                body = re.sub(r'\s+', ' ', unit.get('body') or '')
                for sentence in re.split(r'(?<=[.!?])\s+', body):
                    sentence = clean_source(sentence)
                    if not (55 <= len(sentence) <= 280):
                        continue
                    if re.search(r'(?i)\b(self-assessment|exercise|tma|copyright|dear student|turn to|table of contents|learning objectives)\b', sentence):
                        continue
                    if re.match(r'(?i)^(?:summary|introduction|conclusion|references?)\b', sentence):
                        continue
                    signature = re.sub(r'[^a-z0-9]', '', sentence.lower())
                    if signature in seen:
                        continue
                    seen.add(signature)
                    words = re.findall(r'[A-Za-z][A-Za-z-]{4,}', sentence)
                    stop = {'which', 'there', 'their', 'these', 'those', 'because', 'should', 'where', 'about', 'course', 'material'}
                    keywords = []
                    for word in words:
                        if word.lower() not in stop and word.lower() not in {x.lower() for x in keywords}:
                            keywords.append(word)
                        if len(keywords) >= 6:
                            break
                    if len(keywords) >= 2:
                        prompt = professional_prompt(sentence, unit_title)
                        if prompt and not re.search(r'(?i)\b(main concept|concept presented in this section|topic discussed|section)\b', prompt):
                            candidates.append((unit_title, sentence, keywords, prompt))

        random.shuffle(candidates)
        needed = target_count - len(questions)
        for unit_title, sentence, keywords, prompt in candidates[:needed]:
            marks = 5 if len(questions) % 3 else 10
            questions.append({
                'question_text': prompt,
                'question_type': 'essay',
                'correct_answer': sentence,
                'answer_keywords': keywords,
                'marks': marks,
                'explanation': f"Answer guide derived from the official course material ({unit_title}): {sentence}",
                'source': 'generated'
            })

    return questions
