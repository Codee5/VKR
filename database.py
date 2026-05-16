import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'psych_system.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript('''
    CREATE TABLE IF NOT EXISTS school_group (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT NOT NULL,
        class_num INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS student (
        stud_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stud_fullname TEXT NOT NULL,
        stud_psyh_info TEXT,
        group_id INTEGER REFERENCES school_group(group_id),
        psychotype TEXT DEFAULT "Не определён",
        is_healthy INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS group_testing (
        test_id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_date TEXT NOT NULL,
        methodology TEXT NOT NULL,
        group_id INTEGER REFERENCES school_group(group_id)
    );

    CREATE TABLE IF NOT EXISTS test_result (
        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER REFERENCES group_testing(test_id),
        stud_id INTEGER REFERENCES student(stud_id),
        anxiety_score INTEGER NOT NULL,
        result_meaning TEXT NOT NULL,
        cluster INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS individual_consultation (
        ind_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stud_id INTEGER REFERENCES student(stud_id),
        ind_date TEXT NOT NULL,
        problem TEXT NOT NULL,
        psyh_char TEXT,
        recommend TEXT,
        had_problem INTEGER DEFAULT 1
    );
    ''')

    # Seed demo data if empty
    if cur.execute('SELECT COUNT(*) FROM student').fetchone()[0] == 0:
        _seed_demo(cur)

    conn.commit()
    conn.close()

def _seed_demo(cur):
    # Groups
    groups = [('8А', 8), ('8Б', 8), ('7А', 7), ('9В', 9)]
    for g in groups:
        cur.execute('INSERT INTO school_group (group_name, class_num) VALUES (?,?)', g)

    # Students
    students = [
        ('Иванов Александр Петрович',   'Активный, общительный',      1, 'Экстраверт'),
        ('Петрова Мария Сергеевна',      'Замкнутая, тревожная',       1, 'Интроверт'),
        ('Сидоров Кирилл Андреевич',     'Уравновешенный',             1, 'Амбиверт'),
        ('Козлова Екатерина Ивановна',   'Конфликтная, неустойчивая',  1, 'Интроверт'),
        ('Николаев Андрей Николаевич',   'Спокойный, старательный',    2, 'Амбиверт'),
        ('Орлова Анастасия Сергеевна',   'Тревожная перед экзаменами', 2, 'Интроверт'),
        ('Захаров Максим Александрович', 'Гиперактивный',              3, 'Экстраверт'),
        ('Соколова Елена Викторовна',    'Тихая, замкнутая',           3, 'Интроверт'),
        ('Морозов Дмитрий Павлович',     'Лидер, уверенный',           4, 'Экстраверт'),
        ('Кузнецова Ольга Игоревна',     'Неустойчивое настроение',    4, 'Амбиверт'),
    ]
    for s in students:
        cur.execute(
            'INSERT INTO student (stud_fullname, stud_psyh_info, group_id, psychotype) VALUES (?,?,?,?)', s)

    # Testing
    cur.execute(
        "INSERT INTO group_testing (test_date, methodology, group_id) VALUES ('2024-11-15','Шкала тревоги Бека',1)")
    test_id = cur.lastrowid

    results = [
        (1, test_id, 28, 'Невысокая тревога', 1),
        (2, test_id, 52, 'Повышенная тревога', 2),
        (3, test_id, 15, 'Невысокая тревога', 1),
        (4, test_id, 68, 'Очень высокая тревога', 3),
    ]
    for r in results:
        cur.execute(
            'INSERT INTO test_result (stud_id,test_id,anxiety_score,result_meaning,cluster) VALUES (?,?,?,?,?)', r)

    cur.execute(
        "INSERT INTO group_testing (test_date, methodology, group_id) VALUES ('2025-02-20','Тест Пономаренко',2)")
    test_id2 = cur.lastrowid
    results2 = [
        (5, test_id2, 35, 'Невысокая тревога', 1),
        (6, test_id2, 47, 'Повышенная тревога', 2),
    ]
    for r in results2:
        cur.execute(
            'INSERT INTO test_result (stud_id,test_id,anxiety_score,result_meaning,cluster) VALUES (?,?,?,?,?)', r)

    # Consultations
    consultations = [
        (2,  '2024-10-05', 'Тревога перед экзаменами',      'Замкнутость, избегание', 'Индивидуальные занятия',         1),
        (4,  '2024-10-12', 'Буллинг в школе',               'Агрессивность',          'Работа с классом',               1),
        (2,  '2024-11-20', 'Тревога перед экзаменами',      'Тревога нарастает',      'Консультация родителей',         1),
        (6,  '2024-11-25', 'Конфликт с одноклассниками',    'Замкнутость',            'Медиация',                       1),
        (4,  '2025-01-10', 'Буллинг в школе',               'Без изменений',          'Продолжить наблюдение',          1),
        (8,  '2025-01-18', 'Конфликт с родителями',         'Апатия',                 'Семейная консультация',          1),
        (2,  '2025-02-14', 'Тревога перед экзаменами',      'Улучшение',              'Снизить нагрузку',               0),
        (10, '2025-03-01', 'Неустойчивое эмоциональное состояние', 'Перепады настроения', 'Наблюдение',                 1),
        (4,  '2025-03-15', 'Буллинг в школе',               'Ситуация обострилась',   'Привлечь администрацию',         1),
        (6,  '2025-04-02', 'Конфликт с одноклассниками',    'Нормализация',           'Завершить сопровождение',        0),
    ]
    for c in consultations:
        cur.execute(
            'INSERT INTO individual_consultation (stud_id,ind_date,problem,psyh_char,recommend,had_problem) VALUES (?,?,?,?,?,?)', c)
