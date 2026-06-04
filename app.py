"""
四川农业大学2026届研究生毕业晚会 - 节目人气投票系统
Flask + SQLite3
"""

import sqlite3
import os
import csv
import time
from io import StringIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'vote.db'))

CHAPTER_NAMES = {
    1: '第一篇章：青春启幕，声动百甘',
    2: '第二篇章：沃野逐光，艺展芳华',
    3: '第三篇章：研途有声，青春正燃',
    4: '第四篇章：百甘回响，奔赴山海',
    5: '第五篇章：萤窗相照，未来乘风'
}

# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY,
            chapter INTEGER NOT NULL,
            order_num INTEGER NOT NULL,
            program_name TEXT NOT NULL,
            performer TEXT NOT NULL,
            college TEXT NOT NULL,
            category TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS voting_sessions (
            chapter INTEGER PRIMARY KEY,
            is_active INTEGER DEFAULT 0,
            start_time DATETIME,
            duration_minutes INTEGER DEFAULT 5
        );
    """)

    programs = [
        # 篇章一：青春启幕，声动百甘
        (1, 1, 1, '浪漫血液', '金峰臣', '动物医学院', '歌曲'),
        (2, 1, 2, '美丽的神话', '张龄之、徐瑞苑', '商旅学院', '歌曲'),
        (3, 1, 3, '你给我听好', '王琪', '经济学院', '歌曲'),
        (4, 1, 4, '听见下雨的声音', '吴启杭、张又衡、陈浩', '动物科技学院', '歌曲'),
        # 篇章二：沃野逐光，艺展芳华
        (5, 2, 5, '春风十里', '李智强', '林学院', '歌曲'),
        (6, 2, 6, '逐光颂', '于璇璇、吴旻鸿、何沁、符文洋、丁钰会、席茗洁', '动物科技学院', '舞蹈'),
        (7, 2, 7, '海阔天空', '叶朝卿', '水稻研究所', '歌曲'),
        (8, 2, 8, '永不言弃', '艺术团', '校研究生艺术团', '舞蹈'),
        # 篇章三：研途有声，青春正燃
        (9, 3, 9, '风吹麦浪', '石瑾玲、宋佳', '食品学院', '歌曲'),
        (10, 3, 10, '路过人间', '廖远博、何旭颖', '资源学院', '歌曲'),
        (11, 3, 11, '我不知道', '程雨豪', '动物营养研究所', '歌曲'),
        # 篇章四：百甘回响，奔赴山海
        (12, 4, 12, '青春节拍', '张雯涵、胡铭、张嘉宝、毛雯琪、魏芊珣', '艺术与传媒学院', '舞蹈'),
        (13, 4, 13, 'Scarborough Fair', '张佳艺', '管理学院', '歌曲'),
        (14, 4, 14, '我只在乎你', '王成燕', '马克思主义学院', '歌曲'),
        # 篇章五：萤窗相照，未来乘风
        (15, 5, 15, '肆意的河', '王朴', '林学院', '歌曲'),
        (16, 5, 16, '这世界那么多人', '郑洁欣', '经济学院', '舞蹈'),
        (17, 5, 17, '大地之子', '黑来拉批', '理学院', '歌曲'),
    ]

    cur = conn.cursor()
    for p in programs:
        cur.execute(
            "INSERT OR IGNORE INTO programs (id, chapter, order_num, program_name, performer, college, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            p
        )
    for ch in range(1, 6):
        cur.execute(
            "INSERT OR IGNORE INTO voting_sessions (chapter, is_active, duration_minutes) VALUES (?, 0, 5)",
            (ch,)
        )
    conn.commit()
    conn.close()

init_db()

# ---------- Helpers ----------
def get_session_status(chapter):
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM voting_sessions WHERE chapter = ?", (chapter,)
    ).fetchone()
    if not session:
        conn.close()
        return {'is_active': False, 'remaining': 0, 'error': '未找到该篇章'}

    if not session['is_active']:
        conn.close()
        return {'is_active': False, 'remaining': 0, 'error': '投票未开始'}

    start_time = datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
    elapsed = (datetime.now() - start_time).total_seconds()
    total = session['duration_minutes'] * 60

    if elapsed >= total:
        conn.execute(
            "UPDATE voting_sessions SET is_active = 0 WHERE chapter = ?", (chapter,)
        )
        conn.commit()
        conn.close()
        return {'is_active': False, 'remaining': 0, 'error': '投票已结束'}

    conn.close()
    return {
        'is_active': True,
        'remaining': int(total - elapsed) + 1,
        'duration_minutes': session['duration_minutes']
    }

# ---------- Routes ----------
@app.route('/')
def index():
    conn = get_db()
    sessions = conn.execute("SELECT * FROM voting_sessions ORDER BY chapter").fetchall()
    conn.close()
    return render_template('index.html', chapter_names=CHAPTER_NAMES, sessions=sessions)

@app.route('/vote/<int:chapter>')
def vote_page(chapter):
    if chapter < 1 or chapter > 5:
        return '页面不存在', 404

    conn = get_db()
    programs = conn.execute(
        "SELECT * FROM programs WHERE chapter = ? ORDER BY order_num", (chapter,)
    ).fetchall()
    conn.close()

    status = get_session_status(chapter)
    return render_template('vote.html', chapter=chapter, chapter_name=CHAPTER_NAMES[chapter],
                           programs=programs, status=status)

@app.route('/vote/<int:chapter>', methods=['POST'])
def submit_vote(chapter):
    data = request.get_json()
    program_ids = data.get('program_ids', [])

    if not program_ids or not isinstance(program_ids, list) or len(program_ids) == 0:
        return jsonify({'success': False, 'message': '请至少选择一个节目'})

    status = get_session_status(chapter)
    if not status['is_active']:
        return jsonify({'success': False, 'message': status.get('error', '投票未开始或已结束')})

    try:
        conn = get_db()
        for pid in program_ids:
            conn.execute(
                "INSERT INTO votes (program_id, chapter) VALUES (?, ?)",
                (int(pid), chapter)
            )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '投票成功！'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'投票失败：{str(e)}'})

@app.route('/api/status/<int:chapter>')
def api_status(chapter):
    status = get_session_status(chapter)
    return jsonify(status)

# ---------- Admin routes ----------
@app.route('/admin')
def admin_panel():
    conn = get_db()
    sessions = conn.execute("SELECT * FROM voting_sessions ORDER BY chapter").fetchall()
    vote_counts = conn.execute("""
        SELECT p.chapter, p.id, p.program_name, p.performer, p.college, COUNT(v.id) as votes
        FROM programs p LEFT JOIN votes v ON p.id = v.program_id
        GROUP BY p.id ORDER BY p.order_num
    """).fetchall()
    totals = conn.execute("""
        SELECT chapter, COUNT(*) as total_votes
        FROM votes GROUP BY chapter ORDER BY chapter
    """).fetchall()
    conn.close()

    # Generate QR code URLs
    base_url = request.host_url.rstrip('/')

    import qrcode
    from io import BytesIO
    import base64

    qr_codes = {}
    for ch in range(1, 6):
        img = qrcode.make(f'{base_url}/vote/{ch}')
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_codes[ch] = base64.b64encode(buf.getvalue()).decode()

    return render_template('admin.html', chapter_names=CHAPTER_NAMES, sessions=sessions,
                           vote_counts=vote_counts, totals=totals, qr_codes=qr_codes, base_url=base_url)

@app.route('/admin/start/<int:chapter>', methods=['POST'])
def admin_start(chapter):
    duration = request.form.get('duration', 5, type=int)
    conn = get_db()
    conn.execute(
        "UPDATE voting_sessions SET is_active = 1, start_time = datetime('now', 'localtime'), duration_minutes = ? WHERE chapter = ?",
        (duration, chapter)
    )
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/stop/<int:chapter>', methods=['POST'])
def admin_stop(chapter):
    conn = get_db()
    conn.execute("UPDATE voting_sessions SET is_active = 0 WHERE chapter = ?", (chapter,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/reset/<int:chapter>', methods=['POST'])
def admin_reset(chapter):
    conn = get_db()
    conn.execute("DELETE FROM votes WHERE chapter = ?", (chapter,))
    conn.execute("UPDATE voting_sessions SET is_active = 0, start_time = NULL WHERE chapter = ?", (chapter,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/reset-all', methods=['POST'])
def admin_reset_all():
    conn = get_db()
    conn.execute("DELETE FROM votes")
    conn.execute("UPDATE voting_sessions SET is_active = 0, start_time = NULL")
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/results')
def admin_results():
    conn = get_db()
    results = conn.execute("""
        SELECT p.chapter, p.order_num, p.program_name, p.performer, p.college, p.category,
               COUNT(v.id) as votes
        FROM programs p LEFT JOIN votes v ON p.id = v.program_id
        GROUP BY p.id ORDER BY p.chapter, p.order_num
    """).fetchall()
    conn.close()

    chapters = {}
    for r in results:
        ch = r['chapter']
        if ch not in chapters:
            chapters[ch] = {'name': CHAPTER_NAMES[ch], 'programs': []}
        chapters[ch]['programs'].append({
            'order_num': r['order_num'],
            'program_name': r['program_name'],
            'performer': r['performer'],
            'college': r['college'],
            'votes': r['votes']
        })

    # Sort programs by votes descending in each chapter
    for ch in chapters:
        chapters[ch]['programs'].sort(key=lambda x: x['votes'], reverse=True)

    return render_template('results.html', chapters=chapters, chapter_names=CHAPTER_NAMES)

@app.route('/admin/export-csv')
def admin_export_csv():
    conn = get_db()
    results = conn.execute("""
        SELECT p.chapter, p.order_num, p.program_name, p.performer, p.college, p.category,
               COUNT(v.id) as votes
        FROM programs p LEFT JOIN votes v ON p.id = v.program_id
        GROUP BY p.id ORDER BY p.chapter, p.order_num
    """).fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['篇章', '序号', '节目名称', '表演者', '学院', '类型', '票数'])
    for r in results:
        cw.writerow([f'第{r["chapter"]}篇章', r['order_num'], r['program_name'],
                     r['performer'], r['college'], r['category'], r['votes']])

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=vote_results.csv'}
    )

if __name__ == '__main__':
    print("=" * 60)
    print("  四川农业大学研究生毕业晚会 · 投票系统")
    print("=" * 60)
    print(f"  本机地址:          http://localhost:3000")
    print(f"  管理后台:          http://localhost:3000/admin")
    print("=" * 60)
    print("  要让线上观众也能访问，请使用内网穿透工具：")
    print("  推荐: 在 https://natapp.cn 下载 natapp")
    print("  配置: natapp -authtoken=你的token -port=3000")
    print("  或:   在 https://ngrok.com 下载 ngrok")
    print("  配置: ngrok http 3000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=3000, debug=False)
