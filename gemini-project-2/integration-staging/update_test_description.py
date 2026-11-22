from pathlib import Path
p=Path('tests/test_backend.py')
s=p.read_text(encoding='utf-8').replace('def test_strictly_two_tables_architecture(db_session):', 'def test_catalog_and_server_accounts_schema(db_session):').replace('    Требование 1: Количество таблиц строго 2 (никаких промежуточных M2M-таблиц).\n    Таблица 1 — movies.\n    Таблица 2 — categories.', '    Каталог и серверные пользователи с сессиями, без промежуточных M2M-таблиц.')
p.write_text(s,encoding='utf-8')
