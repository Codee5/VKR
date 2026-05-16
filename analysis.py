import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from database import get_db

plt.rcParams['font.family'] = 'DejaVu Sans'

def cluster_chart():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute('''
        SELECT result_meaning, COUNT(*) as cnt
        FROM test_result
        GROUP BY result_meaning
    ''').fetchall()
    conn.close()

    if not rows:
        return None

    labels = [r['result_meaning'] for r in rows]
    sizes  = [r['cnt'] for r in rows]
    color_map = {
        'Невысокая тревога':    '#70AD47',
        'Повышенная тревога':   '#FFD966',
        'Очень высокая тревога':'#FF4444',
    }
    colors = [color_map.get(l, '#AAAAAA') for l in labels]

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct='%1.1f%%', startangle=140,
        wedgeprops=dict(linewidth=1.5, edgecolor='white'),
        pctdistance=0.75)
    for t in autotexts:
        t.set_fontsize(11)
        t.set_fontweight('bold')
        t.set_color('white')
    ax.set_title('Распределение учащихся по кластерам тревожности',
                 fontsize=12, fontweight='bold', pad=12)
    return _fig_to_b64(fig)


def problems_chart():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute('''
        SELECT problem, COUNT(*) as cnt
        FROM individual_consultation
        GROUP BY problem ORDER BY cnt DESC
    ''').fetchall()
    conn.close()

    if not rows:
        return None

    labels = [r['problem'] for r in rows]
    values = [r['cnt'] for r in rows]
    colors = ['#2E75B6','#ED7D31','#A9D18E','#FF4444','#9E9AC8','#FFC000'][:len(labels)]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=110)
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor='white', linewidth=0.8)
    ax.set_xlabel('Количество обращений', fontsize=10)
    ax.set_title('Основные психологические проблемы учащихся', fontsize=12, fontweight='bold', pad=10)
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                str(val), va='center', fontsize=10, fontweight='bold')
    ax.set_xlim(0, max(values) + 1.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    return _fig_to_b64(fig)


def get_analysis_stats():
    conn = get_db()
    cur = conn.cursor()
    total = cur.execute('SELECT COUNT(*) as c FROM student').fetchone()['c']
    n_risk = cur.execute(
        'SELECT COUNT(DISTINCT stud_id) as c FROM individual_consultation').fetchone()['c']
    n_cons = cur.execute('SELECT COUNT(*) as c FROM individual_consultation').fetchone()['c']
    n_tests = cur.execute('SELECT COUNT(*) as c FROM group_testing').fetchone()['c']
    dr = round(n_risk / total * 100, 1) if total > 0 else 0
    conn.close()
    return {'total': total, 'n_risk': n_risk, 'n_cons': n_cons, 'n_tests': n_tests, 'dr': dr}


def _fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')
