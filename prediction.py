import numpy as np
from database import get_db

def build_feature_vector(stud_id, date_from=None, date_to=None):
    """Build feature vector x1-x7 for a student."""
    conn = get_db()
    cur = conn.cursor()

    # x1: last anxiety score
    row = cur.execute(
        'SELECT anxiety_score, cluster FROM test_result WHERE stud_id=? ORDER BY result_id DESC LIMIT 1',
        (stud_id,)).fetchone()
    x1 = row['anxiety_score'] if row else 30
    x4 = row['cluster'] if row else 1

    # x2: number of consultations in period
    query = 'SELECT COUNT(*) as cnt FROM individual_consultation WHERE stud_id=?'
    params = [stud_id]
    if date_from and date_to:
        query += ' AND ind_date BETWEEN ? AND ?'
        params += [date_from, date_to]
    x2 = cur.execute(query, params).fetchone()['cnt']

    # x3: anxiety dynamics (current - previous score)
    scores = cur.execute(
        'SELECT anxiety_score FROM test_result WHERE stud_id=? ORDER BY result_id DESC LIMIT 2',
        (stud_id,)).fetchall()
    x3 = 0
    if len(scores) == 2:
        x3 = scores[0]['anxiety_score'] - scores[1]['anxiety_score']

    # x5: psychotype encoded
    row5 = cur.execute('SELECT psychotype FROM student WHERE stud_id=?', (stud_id,)).fetchone()
    ptype_map = {'Экстраверт': 0, 'Амбиверт': 1, 'Интроверт': 2, 'Не определён': 1}
    x5 = ptype_map.get(row5['psychotype'] if row5 else 'Не определён', 1)

    # x6: unique problem types
    x6 = cur.execute(
        'SELECT COUNT(DISTINCT problem) as cnt FROM individual_consultation WHERE stud_id=?',
        (stud_id,)).fetchone()['cnt']

    # x7: class number
    row7 = cur.execute(
        'SELECT sg.class_num FROM student s JOIN school_group sg ON s.group_id=sg.group_id WHERE s.stud_id=?',
        (stud_id,)).fetchone()
    x7 = row7['class_num'] if row7 else 8

    conn.close()
    return [x1, x2, x3, x4, x5, x6, x7]


def get_training_data():
    """Build training dataset from consultation history."""
    conn = get_db()
    cur = conn.cursor()
    students = cur.execute('SELECT stud_id FROM student').fetchall()

    X, y = [], []
    for s in students:
        sid = s['stud_id']
        vec = build_feature_vector(sid)
        # Target: had any problem in recent consultations
        had = cur.execute(
            'SELECT MAX(had_problem) as hp FROM individual_consultation WHERE stud_id=?',
            (sid,)).fetchone()['hp']
        y_val = had if had is not None else 0
        X.append(vec)
        y.append(y_val)

    conn.close()
    return np.array(X, dtype=float), np.array(y)


def normalize(X, x_min=None, x_max=None):
    if x_min is None:
        x_min = X.min(axis=0)
        x_max = X.max(axis=0)
    denom = (x_max - x_min)
    denom[denom == 0] = 1
    return (X - x_min) / denom, x_min, x_max


def gini_impurity(y):
    if len(y) == 0:
        return 0
    p1 = np.mean(y)
    return 1 - p1**2 - (1-p1)**2


class SimpleDecisionTree:
    """Simple Decision Tree for binary classification (max_depth=5, criterion=gini)."""
    def __init__(self, max_depth=5):
        self.max_depth = max_depth
        self.tree = None

    def fit(self, X, y):
        self.tree = self._build(X, y, depth=0)

    def _build(self, X, y, depth):
        if depth >= self.max_depth or len(set(y)) == 1 or len(y) < 2:
            return {'leaf': True, 'prob': float(np.mean(y))}

        best_feat, best_thresh, best_gini = None, None, float('inf')
        for feat in range(X.shape[1]):
            thresholds = np.unique(X[:, feat])
            for t in thresholds:
                left_y  = y[X[:, feat] <= t]
                right_y = y[X[:, feat] >  t]
                if len(left_y) == 0 or len(right_y) == 0:
                    continue
                g = (len(left_y)*gini_impurity(left_y) + len(right_y)*gini_impurity(right_y)) / len(y)
                if g < best_gini:
                    best_gini, best_feat, best_thresh = g, feat, t

        if best_feat is None:
            return {'leaf': True, 'prob': float(np.mean(y))}

        mask = X[:, best_feat] <= best_thresh
        return {
            'leaf': False, 'feat': best_feat, 'thresh': best_thresh,
            'left':  self._build(X[mask],  y[mask],  depth+1),
            'right': self._build(X[~mask], y[~mask], depth+1),
            'importance': best_gini
        }

    def predict_proba(self, x):
        node = self.tree
        while not node['leaf']:
            if x[node['feat']] <= node['thresh']:
                node = node['left']
            else:
                node = node['right']
        return node['prob']


_model = None
_x_min = None
_x_max = None
_f1 = None

def train_model():
    global _model, _x_min, _x_max, _f1
    X, y = get_training_data()
    if len(X) < 5:
        return None, 0.0

    X_norm, _x_min, _x_max = normalize(X)

    # Simple train/test split (80/20)
    n = len(X_norm)
    split = max(1, int(n * 0.8))
    X_tr, X_te = X_norm[:split], X_norm[split:]
    y_tr, y_te = y[:split],     y[split:]

    _model = SimpleDecisionTree(max_depth=5)
    _model.fit(X_tr, y_tr)

    if len(X_te) > 0:
        preds = [1 if _model.predict_proba(x) >= 0.5 else 0 for x in X_te]
        tp = sum(1 for p, a in zip(preds, y_te) if p == 1 and a == 1)
        fp = sum(1 for p, a in zip(preds, y_te) if p == 1 and a == 0)
        fn = sum(1 for p, a in zip(preds, y_te) if p == 0 and a == 1)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
        _f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    else:
        _f1 = 0.0

    return _model, _f1


def predict(stud_id):
    global _model, _x_min, _x_max, _f1
    if _model is None:
        train_model()
    if _model is None:
        return None, None

    vec = build_feature_vector(stud_id)
    x = np.array(vec, dtype=float)
    x_norm, _, _ = normalize(x.reshape(1, -1), _x_min, _x_max)
    vp = round(_model.predict_proba(x_norm[0]), 2)

    if vp < 0.30:
        risk = 'Низкий'
        color = 'success'
        rec = 'Плановый мониторинг. Ситуация стабильная.'
    elif vp < 0.60:
        risk = 'Умеренный'
        color = 'warning'
        rec = 'Рекомендуется усилить наблюдение. Запланировать консультацию в течение месяца.'
    elif vp < 0.80:
        risk = 'Высокий'
        color = 'danger'
        rec = 'Высокая вероятность проблемы. Рекомендовано незамедлительное проведение консультации.'
    else:
        risk = 'Критический'
        color = 'danger'
        rec = 'Критический риск! Незамедлительная консультация. Рекомендуется привлечь родителей.'

    return {
        'vp': vp,
        'risk': risk,
        'color': color,
        'recommendation': rec,
        'features': {'x1_тревожность': vec[0], 'x2_консультаций': vec[1],
                     'x3_динамика': vec[2], 'x4_кластер': vec[3],
                     'x6_типов_проблем': vec[5], 'x7_класс': vec[6]},
        'f1': round(_f1, 3) if _f1 else None
    }, vec
