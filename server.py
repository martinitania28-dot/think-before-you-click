#!/usr/bin/env python3
"""
Server per Gioco Cittadinanza Digitale
- Usa Supabase (PostgreSQL) se SUPABASE_URL e SUPABASE_KEY sono impostati
- Altrimenti usa SQLite locale
"""

import json
import sqlite3
import uuid
import re
import os
import mimetypes
import urllib.request as _req
import urllib.parse   as _par
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

BASE_DIR = Path(__file__).parent
PUBLIC   = BASE_DIR
DB_PATH  = BASE_DIR / 'leaderboard.db'
PORT     = int(os.environ.get('PORT', 3000))

# ── Supabase helpers ─────────────────────────────────────────────
SB_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SB_KEY = os.environ.get('SUPABASE_KEY', '')
USE_SB = bool(SB_URL and SB_KEY)

def sb(method, table, data=None, params=None):
    url = SB_URL + '/rest/v1/' + table
    if params:
        url += '?' + _par.urlencode(params, doseq=True)
    headers = {
        'apikey': SB_KEY,
        'Authorization': 'Bearer ' + SB_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }
    body = json.dumps(data).encode() if data is not None else None
    r = _req.Request(url, data=body, headers=headers, method=method)
    try:
        with _req.urlopen(r) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else []
    except _req.HTTPError as e:
        print('Supabase error:', e.code, e.read().decode(errors='replace'))
        return None
    except Exception as e:
        print('Supabase error:', e)
        return None

# ── SQLite helpers ───────────────────────────────────────────────
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    if USE_SB:
        print('Storage: Supabase')
        return
    print('Storage: SQLite (local)')
    with get_db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            nickname TEXT UNIQUE NOT NULL COLLATE NOCASE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS game_sessions (
            id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            duration_s INTEGER,
            completed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS item_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            correct INTEGER NOT NULL,
            chosen TEXT
        );
        """)

init_db()

# ── Config ───────────────────────────────────────────────────────
CONFIG_PY   = BASE_DIR / 'game_config.py'
CONFIG_JSON = BASE_DIR / 'game_config.json'

def load_config():
    if CONFIG_PY.exists():
        spec = spec_from_file_location('game_config', CONFIG_PY)
        mod  = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.CONFIG
    if CONFIG_JSON.exists():
        return json.loads(CONFIG_JSON.read_text())
    raise FileNotFoundError('game_config.py not found')

def get_config():
    return load_config()

CONFIG = load_config()

# ── HTTP Handler ─────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print("  %s %s" % (self.address_string(), fmt % args))

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length))

    def send_static(self, path):
        if not path.exists():
            self.send_response(404); self.end_headers(); return
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime or 'application/octet-stream')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    # ── GET ──────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/upload':         return self.serve_upload_page()
        if path == '/api/config':     return self.api_config()
        if path == '/api/leaderboard':return self.api_leaderboard()
        if path == '/api/export':     return self.api_export()

        if path in ('/', ''):
            return self.send_static(PUBLIC / 'index.html')

        fp = PUBLIC / path.lstrip('/')
        try:
            fp.resolve().relative_to(PUBLIC.resolve())
        except ValueError:
            self.send_response(403); self.end_headers(); return
        self.send_static(fp)

    # ── POST ─────────────────────────────────────────────────────
    def do_POST(self):
        path = self.path.split('?')[0]
        if path == '/api/register': return self.api_register()
        if path == '/api/submit':   return self.api_submit()
        if path == '/upload':       return self.api_upload()
        self.send_response(404); self.end_headers()

    # ── API: config ──────────────────────────────────────────────
    def api_config(self):
        cfg = get_config()
        safe = {
            'title':      cfg['title'],
            'subtitle':   cfg['subtitle'],
            'categories': cfg['categories'],
            'items': [{
                'id':      i['id'],
                'name':    i.get('name', ''),
                'author':  i.get('author', ''),
                'image':   i.get('image'),
                'text':    i.get('text', ''),
                'correct': i['correct'],
            } for i in cfg['items']],
        }
        self.send_json(safe)

    # ── API: register ────────────────────────────────────────────
    def api_register(self):
        try:
            body = self.read_json()
            nick = (body.get('nickname') or '').strip()
        except Exception:
            return self.send_json({'error': 'JSON non valido.'}, 400)

        if len(nick) < 2 or len(nick) > 30:
            return self.send_json({'error': 'Nickname 2-30 caratteri.'}, 400)

        if USE_SB:
            rows = sb('GET', 'players',
                      params={'select': 'id', 'nickname': 'ilike.' + nick})
            if rows:
                return self.send_json({'playerId': rows[0]['id'], 'isNew': False})
            pid = str(uuid.uuid4())
            sb('POST', 'players', data={'id': pid, 'nickname': nick})
            return self.send_json({'playerId': pid, 'isNew': True})

        with get_db() as con:
            row = con.execute(
                'SELECT id FROM players WHERE nickname = ?', (nick,)).fetchone()
            if row:
                return self.send_json({'playerId': row['id'], 'isNew': False})
            pid = str(uuid.uuid4())
            con.execute('INSERT INTO players (id, nickname) VALUES (?,?)', (pid, nick))
        self.send_json({'playerId': pid, 'isNew': True})

    # ── API: submit ──────────────────────────────────────────────
    def api_submit(self):
        try:
            body      = self.read_json()
            player_id = body.get('playerId')
            results   = body.get('results', [])
            duration  = body.get('durationSeconds')
        except Exception:
            return self.send_json({'error': 'JSON non valido.'}, 400)

        if not player_id or not isinstance(results, list):
            return self.send_json({'error': 'Dati mancanti.'}, 400)

        cfg      = get_config()
        corr_map = {i['id']: i['correct'] for i in cfg['items']}

        validated = []
        for r in results:
            item_id = r.get('itemId', '')
            chosen  = r.get('chosen', '')
            correct = 1 if corr_map.get(item_id) == chosen else 0
            validated.append((item_id, chosen, correct))

        score = sum(v[2] for v in validated)
        sid   = str(uuid.uuid4())

        if USE_SB:
            rows = sb('GET', 'players',
                      params={'select': 'id', 'id': 'eq.' + player_id})
            if not rows:
                return self.send_json({'error': 'Giocatore non trovato.'}, 404)
            sb('POST', 'game_sessions', data={
                'id': sid, 'player_id': player_id,
                'score': score, 'total': len(cfg['items']), 'duration_s': duration
            })
            sb('POST', 'item_results', data=[
                {'session_id': sid, 'item_id': v[0], 'chosen': v[1], 'correct': v[2]}
                for v in validated
            ])
            return self.send_json({'score': score, 'total': len(cfg['items'])})

        with get_db() as con:
            if not con.execute(
                    'SELECT id FROM players WHERE id=?', (player_id,)).fetchone():
                return self.send_json({'error': 'Giocatore non trovato.'}, 404)
            con.execute(
                'INSERT INTO game_sessions (id,player_id,score,total,duration_s)'
                ' VALUES (?,?,?,?,?)',
                (sid, player_id, score, len(cfg['items']), duration))
            con.executemany(
                'INSERT INTO item_results (session_id,item_id,chosen,correct)'
                ' VALUES (?,?,?,?)',
                [(sid, v[0], v[1], v[2]) for v in validated])

        self.send_json({'score': score, 'total': len(cfg['items'])})

    # ── API: leaderboard ─────────────────────────────────────────
    def api_leaderboard(self):
        if USE_SB:
            players_rows  = sb('GET', 'players',
                               params={'select': 'id,nickname'}) or []
            sessions_rows = sb('GET', 'game_sessions',
                               params={'select': 'player_id,score,total,duration_s'}) or []
            items_rows    = sb('GET', 'item_results',
                               params={'select': 'item_id,correct'}) or []

            # aggregate players
            pid_nick = {p['id']: p['nickname'] for p in players_rows}
            agg = {}
            for s in sessions_rows:
                pid = s['player_id']
                if pid not in agg:
                    agg[pid] = {'best_score': 0, 'total': s['total'],
                                'partite': 0, 'best_time_s': None}
                a = agg[pid]
                a['best_score'] = max(a['best_score'], s['score'])
                a['total']      = s['total']
                a['partite']   += 1
                t = s['duration_s']
                if t is not None:
                    a['best_time_s'] = t if a['best_time_s'] is None \
                                       else min(a['best_time_s'], t)

            players_out = sorted([
                {'nickname':    pid_nick.get(pid, pid),
                 'best_score':  a['best_score'],
                 'total':       a['total'],
                 'partite':     a['partite'],
                 'best_time_s': a['best_time_s']}
                for pid, a in agg.items()
            ], key=lambda x: (-x['best_score'],
                               x['best_time_s'] if x['best_time_s'] is not None else 9999))

            # aggregate items
            iagg = {}
            for ir in items_rows:
                iid = ir['item_id']
                if iid not in iagg:
                    iagg[iid] = {'tentativi': 0, 'corretti': 0}
                iagg[iid]['tentativi'] += 1
                iagg[iid]['corretti']  += ir['correct']

            cfg      = get_config()
            name_map = {i['id']: i for i in cfg['items']}
            items_out = sorted([
                {'item_id':   iid,
                 'tentativi': v['tentativi'],
                 'corretti':  v['corretti'],
                 'pct':       round(v['corretti']/v['tentativi']*100) if v['tentativi'] else 0,
                 'text':      name_map.get(iid, {}).get('text', iid),
                 'image':     name_map.get(iid, {}).get('image')}
                for iid, v in iagg.items()
            ], key=lambda x: -x['corretti'])

            return self.send_json({'players': players_out, 'items': items_out})

        # SQLite
        with get_db() as con:
            players = con.execute("""
                SELECT p.nickname,
                       MAX(gs.score)      AS best_score,
                       gs.total           AS total,
                       COUNT(gs.id)       AS partite,
                       MIN(gs.duration_s) AS best_time_s
                FROM players p
                JOIN game_sessions gs ON gs.player_id = p.id
                GROUP BY p.id
                ORDER BY best_score DESC, best_time_s ASC
                LIMIT 100""").fetchall()
            raw_items = con.execute("""
                SELECT item_id, COUNT(*) AS tentativi, SUM(correct) AS corretti
                FROM item_results
                GROUP BY item_id
                ORDER BY corretti DESC""").fetchall()

        cfg      = get_config()
        name_map = {i['id']: i for i in cfg['items']}
        items_out = [{
            'item_id':   r['item_id'],
            'tentativi': r['tentativi'],
            'corretti':  r['corretti'],
            'pct':       round(r['corretti']/r['tentativi']*100) if r['tentativi'] else 0,
            'text':      name_map.get(r['item_id'], {}).get('text', r['item_id']),
            'image':     name_map.get(r['item_id'], {}).get('image'),
        } for r in raw_items]

        self.send_json({'players': [dict(p) for p in players], 'items': items_out})

    # ── API: export CSV ──────────────────────────────────────────
    def api_export(self):
        import io, csv
        if USE_SB:
            players_rows  = sb('GET', 'players',
                               params={'select': 'id,nickname'}) or []
            sessions_rows = sb('GET', 'game_sessions',
                               params={'select': 'player_id,score,total,duration_s,completed_at'}) or []
            items_rows    = sb('GET', 'item_results',
                               params={'select': 'item_id,correct'}) or []
            pid_nick = {p['id']: p['nickname'] for p in players_rows}
            sessions = [{'nickname':    pid_nick.get(r['player_id'], '?'),
                         'score':       r['score'],
                         'total':       r['total'],
                         'duration_s':  r['duration_s'],
                         'completed_at':r['completed_at']}
                        for r in sessions_rows]
            iagg = {}
            for ir in items_rows:
                iid = ir['item_id']
                if iid not in iagg:
                    iagg[iid] = {'tentativi': 0, 'corretti': 0}
                iagg[iid]['tentativi'] += 1
                iagg[iid]['corretti']  += ir['correct']
        else:
            with get_db() as con:
                rows = con.execute("""
                    SELECT p.nickname, gs.score, gs.total, gs.duration_s, gs.completed_at
                    FROM game_sessions gs JOIN players p ON p.id=gs.player_id
                    ORDER BY gs.completed_at DESC""").fetchall()
                sessions = [dict(r) for r in rows]
                ir_rows  = con.execute("""
                    SELECT item_id, COUNT(*) AS tentativi, SUM(correct) AS corretti
                    FROM item_results GROUP BY item_id""").fetchall()
                iagg = {r['item_id']: {'tentativi': r['tentativi'],
                                       'corretti':  r['corretti']}
                        for r in ir_rows}

        cfg      = get_config()
        name_map = {i['id']: i.get('name', i['id']) for i in cfg['items']}

        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerow(['Artwork', 'Correct answers', 'Total attempts', 'Accuracy'])
        # sort by accuracy descending
        sorted_items = sorted(
            iagg.items(),
            key=lambda x: -(x[1]['corretti']/x[1]['tentativi'] if x[1]['tentativi'] else 0)
        )
        for iid, v in sorted_items:
            pct = round(v['corretti']/v['tentativi']*100) if v['tentativi'] else 0
            w.writerow([name_map.get(iid, iid),
                        v['corretti'], v['tentativi'], str(pct)+'%'])

        data = buf.getvalue().encode('utf-8-sig')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="risultati.csv"')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    # ── Upload page ──────────────────────────────────────────────
    def serve_upload_page(self):
        html = (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Upload Images</title>'
            '<style>'
            '*{box-sizing:border-box;margin:0;padding:0}'
            'body{font-family:system-ui,sans-serif;background:#f0f4f8;min-height:100vh;'
            '     display:flex;align-items:center;justify-content:center;padding:24px}'
            '.card{background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.1);'
            '      padding:40px 32px;max-width:520px;width:100%;text-align:center}'
            'h1{font-size:1.5rem;margin-bottom:8px}'
            'p{color:#718096;margin-bottom:24px;font-size:.95rem}'
            '.drop{border:2px dashed #cbd5e0;border-radius:12px;padding:32px 16px;'
            '      margin-bottom:20px;cursor:pointer;background:#f7fafc}'
            '.drop input{display:none}'
            '.drop-label{font-size:1rem;color:#4a5568}'
            '.drop-sub{font-size:.82rem;color:#a0aec0;margin-top:6px}'
            '.btn{width:100%;padding:14px;background:#4299e1;color:#fff;border:none;'
            '     border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer}'
            '#status{margin-top:16px;font-size:.9rem;min-height:24px}'
            '.ok{color:#38a169}.err{color:#e53e3e}'
            '#file-list{text-align:left;margin:12px 0;font-size:.82rem;color:#4a5568;'
            '           max-height:160px;overflow-y:auto}'
            '#file-list div{padding:2px 0;border-bottom:1px solid #f0f4f8}'
            '</style></head><body>'
            '<div class="card">'
            '<h1>Upload Images</h1>'
            '<p>Select all artwork photos and logos at once.<br>'
            'Allowed: .jpg .jpeg .png | Max 10 MB per file</p>'
            '<form id="form" enctype="multipart/form-data">'
            '<div class="drop" onclick="document.getElementById(\'files\').click()">'
            '<input type="file" id="files" name="files" multiple accept=".jpg,.jpeg,.png">'
            '<div class="drop-label">Click to choose files</div>'
            '<div class="drop-sub">Select all images at once</div>'
            '</div>'
            '<div id="file-list"></div>'
            '<button class="btn" type="submit">Upload all</button>'
            '</form>'
            '<div id="status"></div>'
            '</div>'
            '<script>'
            'var inp=document.getElementById("files");'
            'var lst=document.getElementById("file-list");'
            'inp.addEventListener("change",function(){'
            '  lst.innerHTML="";'
            '  for(var i=0;i<inp.files.length;i++){'
            '    var d=document.createElement("div");'
            '    d.textContent=inp.files[i].name+" ("+(inp.files[i].size/1024).toFixed(0)+" KB)";'
            '    lst.appendChild(d);'
            '  }'
            '});'
            'document.getElementById("form").addEventListener("submit",async function(e){'
            '  e.preventDefault();'
            '  var st=document.getElementById("status");'
            '  if(!inp.files.length){st.className="err";st.textContent="No files selected.";return;}'
            '  st.className="";st.textContent="Uploading...";'
            '  var fd=new FormData();'
            '  for(var i=0;i<inp.files.length;i++){fd.append("files",inp.files[i]);}'
            '  try{'
            '    var r=await fetch("/upload",{method:"POST",body:fd});'
            '    var d=await r.json();'
            '    if(r.ok){st.className="ok";st.textContent="Done! Saved: "+d.saved.join(", ");}'
            '    else{st.className="err";st.textContent=d.error||"Upload failed.";}'
            '  }catch(err){st.className="err";st.textContent="Network error.";}'
            '});'
            '</script></body></html>'
        )
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    # ── API: upload files ────────────────────────────────────────
    def api_upload(self):
        ALLOWED  = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        MAX_SIZE = 10 * 1024 * 1024
        try:
            ctype = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in ctype:
                return self.send_json({'error': 'Expected multipart/form-data'}, 400)
            boundary = None
            for part in ctype.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip('"').encode()
                    break
            if not boundary:
                return self.send_json({'error': 'No boundary'}, 400)
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            saved, errors = [], []
            for chunk in body.split(b'--' + boundary):
                if b'Content-Disposition' not in chunk:
                    continue
                sep = b'\r\n\r\n' if b'\r\n\r\n' in chunk else b'\n\n'
                if sep not in chunk:
                    continue
                raw_h, fdata = chunk.split(sep, 1)
                m = re.search(r'filename="([^"]+)"',
                              raw_h.decode('utf-8', errors='replace'))
                if not m:
                    continue
                fname = Path(m.group(1)).name
                ext   = Path(fname).suffix.lower()
                if ext not in ALLOWED:
                    errors.append(fname + ': type not allowed'); continue
                fdata = fdata.rstrip(b'\r\n-')
                if len(fdata) > MAX_SIZE:
                    errors.append(fname + ': too large'); continue
                (PUBLIC / fname).write_bytes(fdata)
                saved.append(fname)
            if not saved and errors:
                return self.send_json({'error': '; '.join(errors)}, 400)
            self.send_json({'saved': saved, 'errors': errors})
        except Exception as ex:
            self.send_json({'error': str(ex)}, 500)


# ── Main ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print("\nThink Before You Click")
    print("http://localhost:%d\n" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer fermato.')
