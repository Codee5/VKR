from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import get_db, init_db
from analysis import cluster_chart, problems_chart, get_analysis_stats
from prediction import predict, train_model, _f1
import os

app = Flask(__name__)
app.secret_key = 'psych_system_mvp_2025'

# ── Auth (simple session-less demo) ─────────────────────────────────────────
USERS = {'psycholog': 'lit1533'}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        if USERS.get(u) == p:
            return redirect(url_for('students'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

# ── Students ─────────────────────────────────────────────────────────────────
@app.route('/students')
def students():
    conn = get_db()
    students = conn.execute('''
        SELECT s.*, sg.group_name,
               COUNT(DISTINCT ic.ind_id) as cons_count
        FROM student s
        LEFT JOIN school_group sg ON s.group_id = sg.group_id
        LEFT JOIN individual_consultation ic ON ic.stud_id = s.stud_id
        GROUP BY s.stud_id
        ORDER BY s.stud_fullname
    ''').fetchall()
    conn.close()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    conn = get_db()
    groups = conn.execute('SELECT * FROM school_group ORDER BY class_num, group_name').fetchall()
    if request.method == 'POST':
        conn.execute(
            'INSERT INTO student (stud_fullname, stud_psyh_info, group_id, psychotype) VALUES (?,?,?,?)',
            (request.form['fullname'], request.form['psyh_info'],
             request.form['group_id'], request.form['psychotype']))
        conn.commit()
        conn.close()
        flash('Учащийся добавлен')
        return redirect(url_for('students'))
    conn.close()
    return render_template('student_form.html', groups=groups, student=None)

# ── Consultations ─────────────────────────────────────────────────────────────
@app.route('/consultations')
def consultations():
    conn = get_db()
    cons = conn.execute('''
        SELECT ic.*, s.stud_fullname
        FROM individual_consultation ic
        JOIN student s ON ic.stud_id = s.stud_id
        ORDER BY ic.ind_date DESC
    ''').fetchall()
    conn.close()
    return render_template('consultations.html', consultations=cons)

@app.route('/consultations/add', methods=['GET', 'POST'])
def add_consultation():
    conn = get_db()
    students = conn.execute('SELECT stud_id, stud_fullname FROM student ORDER BY stud_fullname').fetchall()
    PROBLEMS = ['Тревога перед экзаменами', 'Буллинг в школе',
                'Конфликт с одноклассниками', 'Конфликт с родителями',
                'Неустойчивое эмоциональное состояние', 'Другое']
    if request.method == 'POST':
        conn.execute(
            'INSERT INTO individual_consultation (stud_id,ind_date,problem,psyh_char,recommend,had_problem) VALUES (?,?,?,?,?,?)',
            (request.form['stud_id'], request.form['ind_date'],
             request.form['problem'], request.form['psyh_char'],
             request.form['recommend'], 1))
        conn.commit()
        conn.close()
        flash('Консультация сохранена')
        return redirect(url_for('consultations'))
    conn.close()
    return render_template('consultation_form.html', students=students, problems=PROBLEMS)

# ── Testing ───────────────────────────────────────────────────────────────────
@app.route('/testing')
def testing():
    conn = get_db()
    tests = conn.execute('''
        SELECT gt.*, sg.group_name, COUNT(tr.result_id) as result_count
        FROM group_testing gt
        JOIN school_group sg ON gt.group_id = sg.group_id
        LEFT JOIN test_result tr ON tr.test_id = gt.test_id
        GROUP BY gt.test_id ORDER BY gt.test_date DESC
    ''').fetchall()
    conn.close()
    return render_template('testing.html', tests=tests)

@app.route('/testing/<int:test_id>')
def testing_detail(test_id):
    conn = get_db()
    test = conn.execute(
        'SELECT gt.*, sg.group_name FROM group_testing gt JOIN school_group sg ON gt.group_id=sg.group_id WHERE gt.test_id=?',
        (test_id,)).fetchone()
    results = conn.execute('''
        SELECT tr.*, s.stud_fullname
        FROM test_result tr JOIN student s ON tr.stud_id=s.stud_id
        WHERE tr.test_id=? ORDER BY tr.anxiety_score DESC
    ''', (test_id,)).fetchall()
    conn.close()
    return render_template('testing_detail.html', test=test, results=results)

@app.route('/testing/add', methods=['GET', 'POST'])
def add_testing():
    conn = get_db()
    groups = conn.execute('SELECT * FROM school_group ORDER BY class_num').fetchall()
    METHODS = ['Шкала тревоги Бека', 'Тест Пономаренко', 'CCT R.Goodman', 'СМОЛ']
    if request.method == 'POST':
        gid = request.form['group_id']
        conn.execute(
            'INSERT INTO group_testing (test_date, methodology, group_id) VALUES (?,?,?)',
            (request.form['test_date'], request.form['methodology'], gid))
        test_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        students = conn.execute('SELECT stud_id FROM student WHERE group_id=?', (gid,)).fetchall()
        import random
        for s in students:
            score = random.randint(10, 75)
            if score < 40: meaning, cluster = 'Невысокая тревога', 1
            elif score < 60: meaning, cluster = 'Повышенная тревога', 2
            else: meaning, cluster = 'Очень высокая тревога', 3
            conn.execute(
                'INSERT INTO test_result (stud_id,test_id,anxiety_score,result_meaning,cluster) VALUES (?,?,?,?,?)',
                (s['stud_id'], test_id, score, meaning, cluster))
        conn.commit()
        conn.close()
        flash(f'Тестирование добавлено, результаты для {len(students)} учащихся сгенерированы')
        return redirect(url_for('testing'))
    conn.close()
    return render_template('testing_form.html', groups=groups, methods=METHODS)

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route('/reports')
def reports():
    stats = get_analysis_stats()
    chart1 = cluster_chart()
    chart2 = problems_chart()
    conn = get_db()
    health_data = conn.execute('''
        SELECT s.stud_fullname, s.psychotype, s.is_healthy,
               GROUP_CONCAT(DISTINCT ic.problem) as problems,
               ic.recommend
        FROM student s
        LEFT JOIN individual_consultation ic ON ic.stud_id=s.stud_id
        GROUP BY s.stud_id ORDER BY s.stud_fullname
    ''').fetchall()
    conn.close()
    return render_template('reports.html', stats=stats,
                           chart1=chart1, chart2=chart2,
                           health_data=health_data)

# ── Prediction ────────────────────────────────────────────────────────────────
@app.route('/prediction')
def prediction():
    conn = get_db()
    students = conn.execute('SELECT stud_id, stud_fullname FROM student ORDER BY stud_fullname').fetchall()
    history = conn.execute('''
        SELECT s.stud_fullname, ic.ind_date, ic.problem,
               COUNT(ic.ind_id) OVER (PARTITION BY ic.stud_id) as total_cons
        FROM individual_consultation ic
        JOIN student s ON ic.stud_id=s.stud_id
        ORDER BY ic.ind_date DESC LIMIT 10
    ''').fetchall()
    conn.close()
    return render_template('prediction.html', students=students,
                           history=history, result=None)

@app.route('/prediction/run', methods=['POST'])
def run_prediction():
    stud_id = int(request.form['stud_id'])
    result, vec = predict(stud_id)
    conn = get_db()
    student = conn.execute('SELECT * FROM student WHERE stud_id=?', (stud_id,)).fetchone()
    students = conn.execute('SELECT stud_id, stud_fullname FROM student ORDER BY stud_fullname').fetchall()
    history = conn.execute('''
        SELECT s.stud_fullname, ic.ind_date, ic.problem,
               COUNT(ic.ind_id) OVER (PARTITION BY ic.stud_id) as total_cons
        FROM individual_consultation ic
        JOIN student s ON ic.stud_id=s.stud_id
        ORDER BY ic.ind_date DESC LIMIT 10
    ''').fetchall()
    conn.close()
    return render_template('prediction.html', students=students,
                           history=history, result=result, student=student)

if __name__ == '__main__':
    init_db()
    train_model()
    app.run(debug=False, port=5050, host='0.0.0.0')
