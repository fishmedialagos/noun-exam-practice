import question_generator as qg


def source_modules():
    body = (
        'Public administration concerns the organisation and management of public institutions.\n'
        'The principles of accountability guide public officials in the exercise of administrative authority.\n'
        'Bureaucracy is a formal system of organisation characterised by hierarchy, rules and specialised functions.\n'
        'Administrative responsibility requires public officers to act in accordance with established laws and procedures.\n'
    ) * 5
    return [{'label': 'Module 1', 'units': [{'label': 'Unit 1', 'title': 'Foundations of Public Administration', 'body': body}]}]


def question_proposals():
    concepts = [
        ('accountability', 'Which principle guides public officials in the exercise of administrative authority?', 'Administrative secrecy', 'Personal discretion', 'Political patronage', 'The principle of __________ guides public officials in exercising administrative authority.'),
        ('bureaucracy', 'Which formal system of organisation is characterised by hierarchy, rules and specialised functions?', 'Informal networking', 'Personal administration', 'Decentralised spontaneity', 'A formal system of organisation characterised by hierarchy and specialised functions is known as __________.'),
        ('hierarchy', 'Which organisational feature establishes levels of authority within a formal administrative structure?', 'Public participation', 'Administrative secrecy', 'Personal autonomy', 'The arrangement of different levels of authority within an organisation is called __________.'),
        ('responsibility', 'Which administrative requirement obliges public officers to act in accordance with established laws and procedures?', 'Political patronage', 'Personal preference', 'Institutional informality', 'Public officers demonstrate administrative __________ when they comply with established laws and procedures.'),
        ('organisation', 'Which management activity is central to the administration of public institutions?', 'Political campaigning', 'Private entertainment', 'Individual leisure', 'The management of public institutions requires effective __________ of people and functions.'),
    ]
    proposals = []
    for i, (answer, stem, b, c, d, fill_stem) in enumerate(concepts):
        proposals.extend([
            {
                'question_type': 'mcq', 'question_text': stem,
                'option_a': answer.capitalize(), 'option_b': b, 'option_c': c, 'option_d': d,
                'correct_answer': answer.capitalize(),
                'explanation': f'The source material identifies {answer} as an important public administration concept.'
            },
            {
                'question_type': 'fill',
                'question_text': fill_stem,
                'option_a': None, 'option_b': None, 'option_c': None, 'option_d': None,
                'correct_answer': answer,
                'explanation': f'The source material identifies {answer} as an important public administration concept.'
            }
        ])
    return proposals


def test_no_ai_key_does_not_create_low_quality_fallback(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert qg.generate_mock_exam_questions(source_modules(), 'PAD101', 'Public Administration', 10) == []


def test_ai_questions_are_validated_balanced_and_intermixed(monkeypatch):
    monkeypatch.setattr(qg, '_call_question_ai', lambda *args, **kwargs: question_proposals())
    result = qg.generate_mock_exam_questions(source_modules(), 'PAD101', 'Public Administration', 10)
    assert len(result) == 10
    assert sum(q['question_type'] == 'mcq' for q in result) == 5
    assert sum(q['question_type'] == 'fill' for q in result) == 5
    assert [q['question_type'] for q in result[:4]] == ['mcq', 'fill', 'mcq', 'fill']
    assert all(q['correct_answer'] in 'ABCD' for q in result if q['question_type'] == 'mcq')
    assert all(q['correct_answer'] in {'accountability', 'bureaucracy', 'hierarchy', 'responsibility', 'organisation'} for q in result if q['question_type'] == 'fill')


def test_mcq_with_duplicate_options_is_rejected():
    source = {'module': 'Module 1', 'unit': 'Unit 1', 'title': 'Public Administration',
              'text': 'Public administration concerns the organisation and management of public institutions and administrative authority.'}
    raw = {
        'question_type': 'mcq',
        'question_text': 'Which concept describes the organisation and management of public institutions in this academic discipline?',
        'option_a': 'Public administration', 'option_b': 'Public administration',
        'option_c': 'Bureaucracy', 'option_d': 'Accountability',
        'correct_answer': 'Public administration',
        'explanation': 'The source material defines the scope of public administration.'
    }
    assert qg._validate(raw, source, set()) is None


def test_fill_question_requires_a_source_supported_term():
    source = {'module': 'Module 1', 'unit': 'Unit 1', 'title': 'Public Administration',
              'text': 'Public administration concerns the organisation and management of public institutions and administrative authority.'}
    raw = {
        'question_type': 'fill',
        'question_text': 'Public administration concerns the __________ of public institutions and administrative authority.',
        'correct_answer': 'management',
        'explanation': 'The source material explains the management role of public administration.'
    }
    assert qg._validate(raw, source, set()) is not None
    raw['correct_answer'] = 'moonlighting'
    assert qg._validate(raw, source, set()) is None


def test_openai_is_preferred_when_both_keys_are_configured(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('GROQ_API_KEY', 'test-groq-key')
    monkeypatch.delenv('QUESTION_AI_PROVIDER', raising=False)
    settings = qg._api_settings()
    assert settings[0] == 'https://api.openai.com/v1/chat/completions'
    assert settings[1] == 'test-openai-key'
    assert settings[2] == 'gpt-4o-mini'


def test_openai_provider_can_be_forced(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('GROQ_API_KEY', 'test-groq-key')
    monkeypatch.setenv('QUESTION_AI_PROVIDER', 'openai')
    assert qg._api_settings()[0] == 'https://api.openai.com/v1/chat/completions'
