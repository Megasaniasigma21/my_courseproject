from pathlib import Path
for name in ['backend/models.py','backend/database.py']:
 p=Path(name)
 s=p.read_text(encoding='utf-8')
 start=s.index('"""')
 end=s.index('"""',start+3)+3
 doc='Модели каталога, пользователей и серверных сессий.' if 'models' in name else 'SQLite: каталог, зашифрованные профили и серверные сессии.'
 s=s[:start]+'"""'+doc+'"""'+s[end:]
 s=s.replace('Миграция схемы SQLite строго под 2 таблицы:', 'Миграция схемы каталога; таблицы пользователей и сессий создаются из моделей:').replace('# 1. СТРОГО 2 таблицы: удаляем промежуточную M2M таблицу', '# Обратная совместимость со старой схемой каталога').replace('# 2. Создаем таблицы models (movies, categories), если их еще нет', '# Создаём все таблицы моделей, если их ещё нет')
 p.write_text(s,encoding='utf-8')
p=Path('integration-staging/gradle.properties')
s=p.read_text(encoding='utf-8').replace('http://192.168.68.105:8000/api/','http://10.0.2.2:8000/api/')
p.write_text(s,encoding='utf-8')
