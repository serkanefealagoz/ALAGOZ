from flask import Flask, render_template_string, redirect, url_for, request, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz-mukemmel-sistem-anahtari'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Anlık online kullanıcı takibi
online_users = set()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(255), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# --- HTML ŞABLONLARI (Tek dosya içinde modern ve şık arayüz) ---

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ - Giriş</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center h-screen px-4 font-sans">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-3xl shadow-2xl w-full max-w-md">
        <div class="text-center mb-6">
            <h1 class="text-3xl font-black text-indigo-400">ALAGÖZ</h1>
            <p class="text-xs text-slate-400 mt-1">Güvenli Haberleşme Paneli</p>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="mb-4 p-3 text-xs rounded-xl bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-center">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-slate-400 uppercase mb-1">Kimlik Numarası (ID)</label>
                <input type="text" name="custom_id" required placeholder="Örn: 482910" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:outline-none focus:border-indigo-500 text-sm text-slate-200">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-400 uppercase mb-1">Şifre</label>
                <input type="password" name="password" required class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:outline-none focus:border-indigo-500 text-sm text-slate-200">
            </div>
            <button type="submit" class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-sm transition shadow-lg shadow-indigo-600/30">Giriş Yap</button>
        </form>
        <p class="mt-6 text-center text-xs text-slate-400">Hesabın yok mu? <a href="/register" class="text-indigo-400 hover:underline font-semibold">Kayıt Ol</a></p>
    </div>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ - Kayıt</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center h-screen px-4 font-sans">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-3xl shadow-2xl w-full max-w-md">
        <div class="text-center mb-6">
            <h1 class="text-3xl font-black text-indigo-400">ALAGÖZ</h1>
            <p class="text-xs text-slate-400 mt-1">Yeni Hesap Oluştur</p>
        </div>
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-slate-400 uppercase mb-1">Adınız / Rumuzunuz</label>
                <input type="text" name="username" required placeholder="Adınız" class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:outline-none focus:border-indigo-500 text-sm text-slate-200">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-400 uppercase mb-1">Şifre</label>
                <input type="password" name="password" required class="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:outline-none focus:border-indigo-500 text-sm text-slate-200">
            </div>
            <button type="submit" class="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold text-sm transition shadow-lg shadow-emerald-600/30">Kayıt Ol ve ID Al</button>
        </form>
        <p class="mt-6 text-center text-xs text-slate-400">Zaten hesabın var mı? <a href="/login" class="text-indigo-400 hover:underline font-semibold">Giriş Yap</a></p>
    </div>
</body>
</html>
"""

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ - Sohbet</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body class="bg-slate-950 text-slate-100 h-screen flex flex-col font-sans overflow-hidden">
    
    <!-- Üst Bar -->
    <header class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex justify-between items-center shadow-lg z-20">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-white shadow-md shadow-indigo-600/30">A</div>
            <div>
                <h1 class="text-sm font-black tracking-wider text-indigo-400">ALAGÖZ</h1>
                <span class="text-xs text-slate-400">ID'niz: <strong class="text-emerald-400 font-mono">{{ current_user.custom_id }}</strong> ({{ current_user.username }})</span>
            </div>
        </div>
        <a href="/logout" class="bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white px-4 py-2 rounded-xl text-xs font-semibold transition border border-red-500/20">Çıkış</a>
    </header>

    <!-- Ana Panel -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        <!-- Sol Taraf: Arama ve Tüm Üyeler Listesi -->
        <aside class="w-full md:w-80 bg-slate-900/50 border-r border-slate-800 flex flex-col p-4 gap-3">
            <div class="flex gap-2">
                <input type="text" id="search-id-input" placeholder="ID ile Ara (Örn: 482910)" class="flex-1 px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                <button onclick="searchUser()" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition">Bul</button>
            </div>
            
            <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-1 mt-2">Sistemdeki Üyeler</div>
            <div id="users-list" class="flex-1 overflow-y-auto space-y-2 pr-1">
                <p class="text-xs text-slate-500 text-center mt-4">Yükleniyor...</p>
            </div>
        </aside>

        <!-- Sağ Taraf: Sohbet Alanı -->
        <section class="flex-1 flex flex-col bg-slate-950 relative">
            <div id="chat-header" class="px-6 py-3 bg-slate-900 border-b border-slate-800 text-xs font-bold text-slate-300 hidden flex justify-between items-center z-10">
                <span id="active-chat-title">Sohbet Seçilmedi</span>
                <button id="call-btn" onclick="toggleAudioCall()" class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition shadow-md shadow-emerald-600/20">📞 Sesli Ara</button>
            </div>

            <div id="chat-messages" class="flex-1 p-6 overflow-y-auto space-y-3 flex flex-col">
                <div class="m-auto text-center text-slate-500 text-sm">
                    Sol taraftaki listeden bir üyeye tıkla ya da yukarıdan ID aratarak sohbete başla.
                </div>
            </div>

            <form id="chat-form" onsubmit="sendPrivateMessage(event)" class="p-4 bg-slate-900 border-t border-slate-800 flex gap-3 hidden z-10">
                <input type="text" id="message-input" autocomplete="off" placeholder="Mesajınızı yazın..." class="flex-1 px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm focus:outline-none focus:border-indigo-500 text-slate-200">
                <button type="submit" class="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition">Gönder</button>
            </form>
        </section>
    </div>

    <!-- JavaScript Haberleşme ve Arayüz Kodları -->
    <script>
        const socket = io();
        const myId = "{{ current_user.custom_id }}";
        const myName = "{{ current_user.username }}";
        let targetId = null;
        let localStream = null;
        let peerConnection = null;
        let inCall = false;

        const iceServers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        // Sayfa açıldığında sunucudan tüm kullanıcıları çek
        function fetchUsers() {
            fetch('/get_users')
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    renderUsers(data.users);
                }
            });
        }

        function renderUsers(users) {
            const listDiv = document.getElementById('users-list');
            if(users.length === 0) {
                listDiv.innerHTML = '<p class="text-xs text-slate-500 text-center mt-4">Başka kayıtlı üye yok.</p>';
                return;
            }
            listDiv.innerHTML = '';
            users.forEach(u => {
                const item = document.createElement('div');
                item.className = "p-3 rounded-xl bg-slate-900 border border-slate-800 cursor-pointer hover:bg-slate-800/80 transition flex items-center justify-between group";
                item.onclick = () => startChat(u.custom_id, u.username, u.online);
                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="relative w-9 h-9 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center font-bold text-indigo-400 text-xs">
                            ${u.username[0].toUpperCase()}
                            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-slate-950 ${u.online ? 'bg-emerald-500' : 'bg-slate-600'}"></span>
                        </div>
                        <div>
                            <p class="text-xs font-bold text-slate-200 group-hover:text-indigo-400 transition">${u.username}</p>
                            <p class="text-[10px] text-slate-400 font-mono">ID: ${u.custom_id}</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-slate-500 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">Seç</span>
                `;
                listDiv.appendChild(item);
            });
        }

        setInterval(fetchUsers, 3000); // Her 3 saniyede bir üyeleri ve durumları güncelle
        fetchUsers();

        // ID Arama Butonu
        function searchUser() {
            const queryId = document.getElementById('search-id-input').value.trim();
            if(!queryId) return;

            fetch(`/search_user?id=${queryId}`)
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    startChat(data.custom_id, data.username, data.online);
                } else {
                    alert(data.message);
                }
            });
        }

        function startChat(id, name, isOnline) {
            targetId = id;
            document.getElementById('active-chat-title').innerHTML = `💬 ${name} (ID: ${id}) — <span class="${isOnline ? 'text-emerald-400' : 'text-slate-400'}">${isOnline ? '● Online' : '○ Offline'}</span>`;
            document.getElementById('chat-header').classList.remove('hidden');
            document.getElementById('chat-form').classList.remove('hidden');
            document.getElementById('chat-messages').innerHTML = `<div class="text-center text-xs text-slate-500 my-2">-- Güvenli Birebir Hat Kuruldu --</div>`;
            
            socket.emit('join_room_private', { user1: myId, user2: targetId });
        }

        function sendPrivateMessage(e) {
            e.preventDefault();
            const input = document.getElementById('message-input');
            const msg = input.value.trim();
            if(msg && targetId) {
                socket.emit('send_msg', { sender_id: myId, receiver_id: targetId, sender_name: myName, msg: msg });
                appendMessage(myName, msg, true);
                input.value = '';
            }
        }

        socket.on('receive_msg', function(data) {
            if(data.sender_id === targetId) {
                appendMessage(data.sender_name, data.msg, false);
            }
        });

        function appendMessage(sender, msg, isMe) {
            const chatBox = document.getElementById('chat-messages');
            const div = document.createElement('div');
            div.className = `flex flex-col ${isMe ? 'items-end' : 'items-start'} mb-2`;
            div.innerHTML = `
                <div class="px-4 py-2.5 rounded-2xl max-w-xs text-sm shadow-sm ${isMe ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'}">
                    ${msg}
                </div>
            `;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // Sesli Arama WebRTC
        async function toggleAudioCall() {
            const btn = document.getElementById('call-btn');
            if(!inCall) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    inCall = true;
                    btn.className = "px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-xl text-xs font-bold transition shadow-md shadow-red-600/20";
                    btn.innerText = "🔴 Kapat";
                    
                    setupPeer();
                    const offer = await peerConnection.createOffer();
                    await peerConnection.setLocalDescription(offer);
                    socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'offer', sdp: offer });
                } catch(err) {
                    alert("Mikrofon izni verilmedi!");
                }
            } else {
                hangUp();
            }
        }

        function setupPeer() {
            peerConnection = new RTCPeerConnection(iceServers);
            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
            peerConnection.ontrack = e => {
                const audio = new Audio();
                audio.srcObject = e.streams[0];
                audio.play();
            };
            peerConnection.onicecandidate = e => {
                if(e.candidate) socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'candidate', candidate: e.candidate });
            };
        }

        socket.on('voice', async data => {
            if(!peerConnection) setupPeer();
            if(data.type === 'offer') {
                if(!inCall) {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    localStream.getTracks().forEach(t => peerConnection.addTrack(t, localStream));
                    inCall = true;
                    document.getElementById('call-btn').className = "px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-xl text-xs font-bold transition";
                    document.getElementById('call-btn').innerText = "🔴 Kapat";
                }
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'answer', sdp: answer });
            } else if(data.type === 'answer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
            } else if(data.type === 'candidate') {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });

        function hangUp() {
            if(localStream) localStream.getTracks().forEach(t => t.stop());
            if(peerConnection) peerConnection.close();
            peerConnection = null; localStream = null; inCall = false;
            document.getElementById('call-btn').className = "px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition";
            document.getElementById('call-btn').innerText = "📞 Sesli Ara";
            socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'hangup' });
        }
    </script>
</body>
</html>
"""

# --- ROUTLAR VE BACKEND MANTIĞI ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        custom_id = request.form.get('custom_id', '').strip()
        password = request.form.get('password')
        user = User.query.filter_by(custom_id=custom_id).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            online_users.add(user.custom_id)
            return redirect(url_for('chat'))
        else:
            flash('ID veya şifre hatalı!', 'danger')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        
        generated_id = str(random.randint(100000, 999999))
        while User.query.filter_by(custom_id=generated_id).first():
            generated_id = str(random.randint(100000, 999999))
            
        hashed_password = generate_password_hash(password)
        new_user = User(custom_id=generated_id, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Kayıt Başarılı! ID Numaranız: {generated_id}', 'success')
        return redirect(url_for('login'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/chat')
@login_required
def chat():
    online_users.add(current_user.custom_id)
    return render_template_string(CHAT_TEMPLATE, current_user=current_user)

@app.route('/get_users')
@login_required
def get_users():
    users = User.query.all()
    result = []
    for u in users:
        if u.custom_id != current_user.custom_id:
            result.append({
                'custom_id': u.custom_id,
                'username': u.username,
                'online': u.custom_id in online_users
            })
    return {'success': True, 'users': result}

@app.route('/search_user')
@login_required
def search_user():
    query_id = request.args.get('id', '').strip()
    user = User.query.filter_by(custom_id=query_id).first()
    if user and user.custom_id != current_user.custom_id:
        return {
            'success': True,
            'custom_id': user.custom_id,
            'username': user.username,
            'online': user.custom_id in online_users
        }
    return {'success': False, 'message': 'Kullanıcı bulunamadı.'}

@app.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated:
        online_users.discard(current_user.custom_id)
    logout_user()
    return redirect(url_for('login'))

# --- SOCKET.IO OLAYLARI ---

@socketio.on('join_room_private')
def on_join(data):
    room = ''.join(sorted([str(data['user1']), str(data['user2'])]))
    join_room(room)

@socketio.on('send_msg')
def handle_msg(data):
    room = ''.join(sorted([str(data['sender_id']), str(data['receiver_id'])]))
    emit('receive_msg', {
        'sender_id': data['sender_id'],
        'sender_name': data['sender_name'],
        'msg': data['msg']
    }, room=room)

@socketio.on('voice')
def handle_voice(data):
    room = ''.join(sorted([str(data['sender_id']), str(data['target_id'])]))
    emit('voice', data, room=room, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
