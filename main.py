import socket, hashlib, json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from datetime import datetime

# Простое хранилище в памяти
users = {}
posts = []
messages = []
likes = []
sessions = {}
next_id = 1

CSS = '''<style>
:root{--bg:#0a0a0a;--card:#1a1a1a;--text:#fff;--gray:#888;--accent:#6c5ce7;--accent2:#a855f7}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text)}
.navbar{background:var(--card);padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a2a2a}
.navbar a{color:var(--text);text-decoration:none;margin-left:16px}
.logo{font-size:20px;font-weight:700;background:linear-gradient(135deg,#6c5ce7,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.container{max-width:650px;margin:0 auto;padding:20px}
.card{background:var(--card);padding:20px;border-radius:16px;margin-bottom:16px;border:1px solid #2a2a2a}
.btn{background:linear-gradient(135deg,#6c5ce7,#a855f7);color:#fff;padding:10px 24px;border:none;border-radius:25px;cursor:pointer}
input,textarea{width:100%;padding:12px;margin:8px 0;background:var(--bg);border:1px solid #2a2a2a;border-radius:12px;color:var(--text)}
.avatar{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#6c5ce7,#a855f7);display:flex;align-items:center;justify-content:center;margin-right:12px}
.msg{padding:10px 16px;margin:6px 0;border-radius:20px;max-width:75%}
.sent{background:linear-gradient(135deg,#6c5ce7,#a855f7);margin-left:auto}
.received{background:#2a2a2a}
.chat-box{height:400px;overflow-y:auto;padding:16px}
</style>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        user = self.get_user()
        if path == '/' and user: self.home(user)
        elif path == '/' and not user: self.redirect('/login')
        elif path == '/register': self.page_register()
        elif path == '/login': self.page_login()
        elif path == '/logout': self.logout()
        elif path == '/messages' and user: self.page_messages(user)
        elif path.startswith('/chat/') and user: self.page_chat(user, path.split('/')[-1])
        elif path.startswith('/profile/') and user: self.page_profile(path.split('/')[-1], user)
        elif path == '/explore' and user: self.page_explore(user)
    
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        data = parse_qs(self.rfile.read(length).decode())
        if path == '/register': self.register(data)
        elif path == '/login': self.login(data)
        elif path == '/post': self.create_post(data)
        elif path == '/like': self.like(data)
        elif path == '/message': self.send_message(data)
    
    def get_user(self):
        cookie = self.headers.get('Cookie', '')
        for c in cookie.split(';'):
            if 'session=' in c:
                return sessions.get(c.split('session=')[1].strip())
        return None
    
    def navbar(self, user, title='📱 Messenger'):
        return f'<nav class="navbar"><span class="logo">{title}</span><div><a href="/">Главная</a><a href="/explore">Поиск</a><a href="/messages">Чаты</a><a href="/profile/{user[0]}">Профиль</a><a href="/logout" class="btn" style="padding:6px 16px">Выйти</a></div></nav>'
    
    def home(self, user):
        html = ''
        for p in posts[::-1]:
            author = users.get(str(p['user_id']), {})
            if not author: continue
            is_liked = any(l['user_id'] == user[0] and l['post_id'] == p['id'] for l in likes)
            likes_count = sum(1 for l in likes if l['post_id'] == p['id'])
            html += f'<div class="card"><div class="post-header"><a href="/profile/{p["user_id"]}" style="display:flex;align-items:center;text-decoration:none;color:var(--text)"><div class="avatar">{author["username"][0].upper()}</div><div><b>{author["username"]}</b><div class="time">{p["date"]}</div></div></a></div><div>{p["content"]}</div><button class="btn" style="margin-top:10px" onclick="like({p["id"]})">{"❤️" if is_liked else "🤍"} {likes_count}</button></div>'
        self.send(f'<!DOCTYPE html><html><head><title>Messenger</title>{CSS}</head><body>{self.navbar(user)}<div class="container"><div class="card"><form method="POST" action="/post"><textarea name="content" placeholder="Что нового?" rows="3"></textarea><input name="image" placeholder="Ссылка на фото"><button class="btn" style="width:100%">Опубликовать</button></form></div>{html}</div><script>async function like(id){{await fetch("/like",{{method:"POST",body:new URLSearchParams({{post_id:id}})}});location.reload()}}</script></body></html>')
    
    def page_explore(self, user):
        html = ''
        for uid, u in users.items():
            if int(uid) != user[0]:
                html += f'<a href="/profile/{uid}" style="text-decoration:none;color:var(--text)"><div class="card" style="display:flex;align-items:center"><div class="avatar">{u["username"][0].upper()}</div><b>{u["username"]}</b></div></a>'
        self.send(f'<!DOCTYPE html><html><head><title>Поиск</title>{CSS}</head><body>{self.navbar(user, "🔍 Поиск")}<div class="container">{html or "<p>Никого не найдено</p>"}</div></body></html>')
    
    def page_profile(self, uid, current_user):
        u = users.get(uid)
        if not u: self.send_error(404); return
        user_posts = [p for p in posts if p['user_id'] == int(uid)]
        html = ''.join([f'<div class="card"><div>{p["content"]}</div><div class="time">{p["date"]}</div></div>' for p in user_posts])
        self.send(f'<!DOCTYPE html><html><head><title>{u["username"]}</title>{CSS}</head><body>{self.navbar(current_user, "👤 Профиль")}<div class="container"><div class="card" style="text-align:center"><div class="avatar" style="width:80px;height:80px;font-size:32px;margin:0 auto">{u["username"][0].upper()}</div><h2>@{u["username"]}</h2><a href="/chat/{uid}" class="btn">💬 Написать</a></div>{html}</div></body></html>')
    
    def page_messages(self, user):
        chat_users = set()
        for m in messages:
            if m['from_id'] == user[0]: chat_users.add(m['to_id'])
            if m['to_id'] == user[0]: chat_users.add(m['from_id'])
        html = ''
        for uid in chat_users:
            u = users.get(str(uid))
            if u:
                last_msg = [m for m in messages if (m['from_id']==user[0] and m['to_id']==uid) or (m['from_id']==uid and m['to_id']==user[0])]
                last_text = last_msg[-1]['text'][:40] if last_msg else ''
                html += f'<a href="/chat/{uid}" style="text-decoration:none;color:var(--text)"><div style="display:flex;align-items:center;padding:14px;border-bottom:1px solid #2a2a2a"><div class="avatar">{u["username"][0].upper()}</div><div><b>{u["username"]}</b><p style="color:gray;font-size:13px">{last_text}</p></div></div></a>'
        self.send(f'<!DOCTYPE html><html><head><title>Чаты</title>{CSS}</head><body>{self.navbar(user, "💬 Чаты")}<div class="container"><div class="card">{html or "<p>Нет сообщений</p>"}</div></div></body></html>')
    
    def page_chat(self, user, uid):
        other = users.get(uid)
        if not other: self.send_error(404); return
        chat_msgs = [m for m in messages if (m['from_id']==user[0] and m['to_id']==int(uid)) or (m['from_id']==int(uid) and m['to_id']==user[0])]
        html = ''.join([f'<div class="msg {"sent" if m["from_id"]==user[0] else "received"}">{m["text"]}<div style="font-size:10px;opacity:0.6">{m["date"]}</div></div>' for m in chat_msgs])
        self.send(f'<!DOCTYPE html><html><head><title>Чат</title>{CSS}</head><body><nav class="navbar"><span class="logo">💬 {other["username"]}</span><div><a href="/profile/{uid}">Профиль</a><a href="/messages">Назад</a></div></nav><div class="container"><div class="card"><div class="chat-box" id="msgs">{html}</div><div style="display:flex;gap:8px"><input id="inp" placeholder="Сообщение..." onkeypress="if(event.key===\'Enter\')send()" style="flex:1"><button class="btn" onclick="send()">➤</button></div></div></div><script>document.getElementById("msgs").scrollTop=99999;async function send(){{let v=document.getElementById("inp").value;if(v){{await fetch("/message",{{method:"POST",body:new URLSearchParams({{to:"{uid}",text:v}})}});location.reload()}}}}</script></body></html>')
    
    def page_register(self):
        self.send(f'<!DOCTYPE html><html><head><title>Регистрация</title>{CSS}</head><body><div class="container"><div class="card"><h1 class="logo">📱 Messenger</h1><form method="POST"><input name="username" placeholder="Username" required><input name="email" type="email" placeholder="Email" required><input name="password" type="password" placeholder="Пароль" required><button class="btn" style="width:100%">Зарегистрироваться</button></form><p>Есть аккаунт? <a href="/login">Войти</a></p></div></div></body></html>')
    
    def page_login(self):
        self.send(f'<!DOCTYPE html><html><head><title>Вход</title>{CSS}</head><body><div class="container"><div class="card"><h1 class="logo">📱 Messenger</h1><form method="POST"><input name="email" type="email" placeholder="Email" required><input name="password" type="password" placeholder="Пароль" required><button class="btn" style="width:100%">Войти</button></form><p>Нет аккаунта? <a href="/register">Регистрация</a></p></div></div></body></html>')
    
    def register(self, data):
        global next_id
        username = data['username'][0]
        email = data['email'][0]
        password = hashlib.sha256(data['password'][0].encode()).hexdigest()
        for u in users.values():
            if u['email'] == email or u['username'] == username:
                self.redirect('/register')
                return
        user_id = next_id
        next_id += 1
        users[str(user_id)] = {'id': user_id, 'username': username, 'email': email, 'password': password, 'avatar': ''}
        self.redirect('/login')
    
    def login(self, data):
        email = data['email'][0]
        password = hashlib.sha256(data['password'][0].encode()).hexdigest()
        for uid, u in users.items():
            if u['email'] == email and u['password'] == password:
                sid = hashlib.sha256(os.urandom(32)).hexdigest()
                sessions[sid] = (int(uid), u['username'], u['email'])
                self.send_response(302)
                self.send_header('Set-Cookie', f'session={sid}; Path=/')
                self.send_header('Location', '/')
                self.end_headers()
                return
        self.redirect('/login')
    
    def logout(self):
        self.send_response(302)
        self.send_header('Set-Cookie', 'session=; Path=/; Max-Age=0')
        self.send_header('Location', '/')
        self.end_headers()
    
    def create_post(self, data):
        user = self.get_user()
        if not user: return
        content = data.get('content', [''])[0]
        image = data.get('image', [''])[0]
        posts.append({'id': len(posts)+1, 'user_id': user[0], 'content': content, 'image': image, 'date': datetime.now().strftime('%d.%m.%Y %H:%M')})
        self.redirect('/')
    
    def like(self, data):
        user = self.get_user()
        if not user: return
        post_id = int(data['post_id'][0])
        existing = [l for l in likes if l['user_id'] == user[0] and l['post_id'] == post_id]
        if existing:
            likes.remove(existing[0])
        else:
            likes.append({'user_id': user[0], 'post_id': post_id})
        self.send_json()
    
    def send_message(self, data):
        user = self.get_user()
        if not user: return
        to = int(data['to'][0])
        text = data['text'][0]
        messages.append({'from_id': user[0], 'to_id': to, 'text': text, 'date': datetime.now().strftime('%d.%m.%Y %H:%M')})
        self.send_json()
    
    def send(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_json(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
    
    def redirect(self, url):
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f'Сервер запущен на порту {port}')
    server.serve_forever()
