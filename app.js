const express = require('express');
const Database = require('better-sqlite3');
const path = require('path');
const QRCode = require('qrcode');

const app = express();
const PORT = process.env.PORT || 3000;

// ---------- Database setup ----------
const db = new Database(path.join(__dirname, 'vote.db'));
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
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
    voter_identifier TEXT NOT NULL,
    voter_name TEXT NOT NULL,
    program_id INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    created_at DATETIME DEFAULT (datetime('now', '+8 hours')),
    UNIQUE(voter_identifier, chapter, program_id)
  );

  CREATE TABLE IF NOT EXISTS voting_sessions (
    chapter INTEGER PRIMARY KEY,
    is_active INTEGER DEFAULT 0,
    start_time DATETIME,
    duration_minutes INTEGER DEFAULT 5
  );
`);

// ---------- Seed programs ----------
const programsData = [
  // 第一篇章：青春启幕，声动百廿
  { chapter: 1, order_num: 1, program_name: '浪漫血液', performer: '金峰臣', college: '动物医学院', category: '男子独唱' },
  { chapter: 1, order_num: 2, program_name: '美丽的神话', performer: '张龄之、徐瑞苑', college: '商旅学院', category: '女子合唱' },
  { chapter: 1, order_num: 3, program_name: '你给我听好', performer: '王琪', college: '经济学院', category: '女子独唱' },
  { chapter: 1, order_num: 4, program_name: '听见下雨的声音', performer: '吴启杭、张又衡、陈浩', college: '动物科技学院', category: '男子合唱' },
  // 第二篇章：沃野逐光，艺展芳华
  { chapter: 2, order_num: 5, program_name: '春风十里', performer: '李智强', college: '林学院', category: '吉他弹唱' },
  { chapter: 2, order_num: 6, program_name: '逐光颂', performer: '于璇璇、吴旻鸿、何沁、符文洋、丁钰会、席茗洁', college: '动物科技学院', category: '团队民族舞' },
  // 第三篇章：研途有声，青春正燃
  { chapter: 3, order_num: 7, program_name: '海阔天空', performer: '叶朝卿', college: '水稻研究所', category: '女子独唱' },
  { chapter: 3, order_num: 8, program_name: '风吹麦浪', performer: '石瑾玲、宋佳', college: '食品学院', category: '双人女声合唱' },
  { chapter: 3, order_num: 9, program_name: '路过人间', performer: '廖远博、何旭颖', college: '资源学院', category: '男女合唱' },
  { chapter: 3, order_num: 10, program_name: '我不知道', performer: '程雨豪', college: '动物营养研究所', category: '男子独唱' },
  // 第四篇章：百廿回响，奔赴山海
  { chapter: 4, order_num: 11, program_name: '青春节拍', performer: '张雯涵、胡铭、张嘉宝、毛雯琪、魏芊珣', college: '艺术与传媒学院', category: '群舞Kpop' },
  { chapter: 4, order_num: 12, program_name: 'Scarborough Fair', performer: '张佳艺', college: '管理学院', category: '女子演唱' },
  { chapter: 4, order_num: 13, program_name: '我只在乎你', performer: '王成燕', college: '马克思主义学院', category: '女子独唱' },
  // 第五篇章：萤窗相照，未来乘风
  { chapter: 5, order_num: 14, program_name: '你就不要想起我', performer: '王朴', college: '林学院', category: '男子弹唱' },
  { chapter: 5, order_num: 15, program_name: '这世界那么多人', performer: '郑洁欣', college: '经济学院', category: '舞蹈' },
  { chapter: 5, order_num: 16, program_name: '大地之子', performer: '黑来拉批', college: '理学院', category: '男子弹唱' },
];

const insertProgram = db.prepare(
  'INSERT OR IGNORE INTO programs (id, chapter, order_num, program_name, performer, college, category) VALUES (?, ?, ?, ?, ?, ?, ?)'
);

const insertSession = db.prepare(
  'INSERT OR IGNORE INTO voting_sessions (chapter, is_active, duration_minutes) VALUES (?, 0, 5)'
);

const tx = db.transaction(() => {
  for (const p of programsData) {
    insertProgram.run(p.order_num, p.chapter, p.order_num, p.program_name, p.performer, p.college, p.category);
  }
  for (let ch = 1; ch <= 5; ch++) {
    insertSession.run(ch);
  }
});
tx();

const chapterNames = {
  1: '第一篇章：青春启幕，声动百廿',
  2: '第二篇章：沃野逐光，艺展芳华',
  3: '第三篇章：研途有声，青春正燃',
  4: '第四篇章：百廿回响，奔赴山海',
  5: '第五篇章：萤窗相照，未来乘风'
};

// ---------- Express setup ----------
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'templates'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use('/static', express.static(path.join(__dirname, 'static')));

// ---------- Helper: get voting session with remaining time ----------
function getSessionStatus(chapter) {
  const session = db.prepare('SELECT * FROM voting_sessions WHERE chapter = ?').get(chapter);
  if (!session) return { is_active: false, remaining: 0, error: '未找到该篇章' };
  if (!session.is_active) return { is_active: false, remaining: 0, error: '投票未开始' };

  const start = new Date(session.start_time + '+08:00').getTime();
  const elapsed = (Date.now() - start) / 1000;
  const total = session.duration_minutes * 60;

  if (elapsed >= total) {
    // Auto-close
    db.prepare('UPDATE voting_sessions SET is_active = 0 WHERE chapter = ?').run(chapter);
    return { is_active: false, remaining: 0, error: '投票已结束' };
  }

  return {
    is_active: true,
    remaining: Math.ceil(total - elapsed),
    start_time: session.start_time,
    duration_minutes: session.duration_minutes
  };
}

// ---------- Routes ----------

// Home page
app.get('/', (req, res) => {
  const sessions = db.prepare('SELECT * FROM voting_sessions ORDER BY chapter').all();
  const programs = db.prepare('SELECT * FROM programs ORDER BY order_num').all();
  res.render('index', { chapterNames, sessions, programs });
});

// Voting page for a chapter
app.get('/vote/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  if (chapter < 1 || chapter > 5) return res.status(404).send('页面不存在');

  const programs = db.prepare('SELECT * FROM programs WHERE chapter = ? ORDER BY order_num').all(chapter);
  const status = getSessionStatus(chapter);

  res.render('vote', {
    chapter,
    chapterName: chapterNames[chapter],
    programs,
    status,
    hasVoted: false,
    voterInfo: null
  });
});

// Submit vote
app.post('/vote/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  const { voter_identifier, voter_name, program_ids } = req.body;

  if (!voter_identifier || !voter_name) {
    return res.json({ success: false, message: '请填写学号和姓名' });
  }
  if (!program_ids || (Array.isArray(program_ids) && program_ids.length === 0)) {
    return res.json({ success: false, message: '请至少选择一个节目' });
  }

  const status = getSessionStatus(chapter);
  if (!status.is_active) {
    return res.json({ success: false, message: status.error || '投票未开始或已结束' });
  }

  const ids = Array.isArray(program_ids) ? program_ids : [program_ids];

  // Check if already voted for this chapter
  const existing = db.prepare(
    'SELECT COUNT(*) as cnt FROM votes WHERE voter_identifier = ? AND chapter = ?'
  ).get(voter_identifier, chapter);

  if (existing.cnt > 0) {
    return res.json({ success: false, message: '你已经投过票了，每个篇章只能投一次' });
  }

  // Record votes
  const insertVote = db.prepare(
    'INSERT INTO votes (voter_identifier, voter_name, program_id, chapter) VALUES (?, ?, ?, ?)'
  );

  const submitTx = db.transaction(() => {
    for (const pid of ids) {
      insertVote.run(voter_identifier, voter_name, parseInt(pid), chapter);
    }
  });

  try {
    submitTx();
    return res.json({ success: true, message: '投票成功！' });
  } catch (err) {
    return res.json({ success: false, message: '投票失败：' + err.message });
  }
});

// Check voting status (for client-side timer)
app.get('/api/status/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  const status = getSessionStatus(chapter);
  res.json(status);
});

// Check if voter already voted
app.get('/api/check-voted/:chapter/:identifier', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  const identifier = req.params.identifier;
  const existing = db.prepare(
    'SELECT COUNT(*) as cnt FROM votes WHERE voter_identifier = ? AND chapter = ?'
  ).get(identifier, chapter);
  res.json({ hasVoted: existing.cnt > 0 });
});

// ---------- Admin routes ----------
app.get('/admin', (req, res) => {
  const sessions = db.prepare('SELECT * FROM voting_sessions ORDER BY chapter').all();
  const voteCounts = db.prepare(`
    SELECT p.chapter, p.id, p.program_name, p.performer, p.college, COUNT(v.id) as votes
    FROM programs p LEFT JOIN votes v ON p.id = v.program_id
    GROUP BY p.id ORDER BY p.order_num
  `).all();

  const totals = db.prepare(`
    SELECT chapter, COUNT(DISTINCT voter_identifier) as voters, COUNT(*) as total_votes
    FROM votes GROUP BY chapter ORDER BY chapter
  `).all();

  // Generate QR codes as data URIs
  const baseUrl = req.protocol + '://' + req.get('host');

  res.render('admin', {
    chapterNames,
    sessions,
    voteCounts,
    totals,
    baseUrl,
    QRCode // Pass QRCode module to template
  });
});

app.post('/admin/start/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  const duration = parseInt(req.body.duration) || 5;

  db.prepare(
    'UPDATE voting_sessions SET is_active = 1, start_time = datetime(\'now\', \'+8 hours\'), duration_minutes = ? WHERE chapter = ?'
  ).run(duration, chapter);

  res.redirect('/admin');
});

app.post('/admin/stop/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  db.prepare('UPDATE voting_sessions SET is_active = 0 WHERE chapter = ?').run(chapter);
  res.redirect('/admin');
});

app.post('/admin/reset/:chapter', (req, res) => {
  const chapter = parseInt(req.params.chapter);
  db.prepare('DELETE FROM votes WHERE chapter = ?').run(chapter);
  db.prepare('UPDATE voting_sessions SET is_active = 0, start_time = NULL WHERE chapter = ?').run(chapter);
  res.redirect('/admin');
});

app.get('/admin/results', (req, res) => {
  const results = db.prepare(`
    SELECT p.chapter, p.order_num, p.program_name, p.performer, p.college, p.category,
           COUNT(v.id) as votes
    FROM programs p LEFT JOIN votes v ON p.id = v.program_id
    GROUP BY p.id ORDER BY p.chapter, p.order_num
  `).all();

  const chapters = {};
  for (const r of results) {
    if (!chapters[r.chapter]) {
      chapters[r.chapter] = { name: chapterNames[r.chapter], programs: [] };
    }
    chapters[r.chapter].programs.push(r);
  }

  res.render('results', { chapters, chapterNames });
});

// ---------- Start server ----------
app.listen(PORT, '0.0.0.0', () => {
  console.log(`投票系统已启动: http://localhost:${PORT}`);
  console.log(`管理后台: http://localhost:${PORT}/admin`);
});
