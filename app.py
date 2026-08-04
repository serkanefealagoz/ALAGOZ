import os
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz_secure_ultra_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alagoz_secure.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- VERİTABANI MODELİ ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    custom_id = db.Column(db.String(6), unique=True, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

active_sockets = {}

# --- GİRİŞ / KAYIT / ŞİFREYİ UNUTTUM (ŞIK, ANTRASİT & PROFESYONEL GUI) ---
AUTH_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ — Güvenli İletişim Ağı</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .logo-font { font-family: 'Orbitron', sans-serif; letter-spacing: 2px; }
    </style>
</head>
<body class="bg-[#0b0f19] text-slate-100 h-screen flex items-center justify-center overflow-hidden relative selection:bg-cyan-500 selection:text-white">
    <div class="absolute -top-32 -left-32 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-32 -right-32 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-md p-8 bg-[#131825] border border-slate-800 rounded-3xl shadow-2xl relative z-10 mx-4">
        
        <div class="text-center mb-8">
            <h1 class="logo-font text-2xl font-black text-white tracking-widest">ALAGÖZ</h1>
            <p class="text-xs text-slate-400 font-medium mt-1">
                {% if request.path == '/login' %} Oturum Açma Paneli
                {% elif request.path == '/register' %} Yeni Hesap Kayıt Merkezi
                {% else %} Şifre Kurtarma Modülü {% endif %}
            </p>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="mb-5 p-3.5 {% if category == 'success' %}bg-emerald-500/10 border-emerald-500/30 text-emerald-400{% else %}bg-rose-500/10 border-rose-500/30 text-rose-400{% endif %} border text-xs rounded-xl text-center font-medium">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1.5">Kullanıcı Adı</label>
                <input type="text" name="username" required autocomplete="off" class="w-full px-4 py-3.5 bg-[#0b0f19] border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition shadow-inner">
            </div>

            {% if request.path != '/forgot-password' %}
            <div>
                <label class="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1.5">Şifre</label>
                <input type="password" name="password" required class="w-full px-4 py-3.5 bg-[#0b0f19] border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition shadow-inner">
            </div>
            {% else %}
            <div>
                <label class="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1.5">Yeni Şifre Belirle</label>
                <input type="password" name="new_password" required class="w-full px-4 py-3.5 bg-[#0b0f19] border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition shadow-inner">
            </div>
            {% endif %}

            <button type="submit" class="w-full py-3.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-cyan-600/20 cursor-pointer mt-2">
                {% if request.path == '/login' %} Giriş Yap
                {% elif request.path == '/register' %} Kayıt Ol ve Başla
                {% else %} Şifreyi Sıfırla {% endif %}
            </button>
        </form>

        <div class="mt-6 pt-4 border-t border-slate-800 text-center space-y-2.5">
            {% if request.path == '/login' %}
                <p class="text-xs text-slate-400">Şifrenizi mi unuttunuz? <a href="/forgot-password" class="text-cyan-400 font-bold hover:underline">Şifreyi Sıfırla</a></p>
                <p class="text-xs text-slate-400">Hesabınız yok mu? <a href="/register" class="text-white font-bold hover:underline">Kayıt Ol</a></p>
            {% elif request.path == '/register' %}
                <p class="text-xs text-slate-400">Zaten hesabınız var mı? <a href="/login" class="text-white font-bold hover:underline">Giriş Yap</a></p>
            {% else %}
                <p class="text-xs text-slate-400">Şifrenizi hatırladınız mı? <a href="/login" class="text-cyan-400 font-bold hover:underline">Giriş Ekranına Dön</a></p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# --- CHAT ARAYÜZÜ (ANTRASİT & EKRAN ÇAĞRI PANELİ İLE) ---
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ — İletişim Ağı</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .logo-font { font-family: 'Orbitron', sans-serif; letter-spacing: 1.5px; }
        .custom-scroll::-webkit-scrollbar { width: 5px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #262c3d; border-radius: 10px; }
    </style>
</head>
<body class="bg-[#0b0f19] text-slate-100 h-screen flex flex-col overflow-hidden selection:bg-cyan-500 selection:text-white">
    
    <!-- Üst Bar -->
    <header class="bg-[#131825] border-b border-slate-800 px-6 py-3.5 flex justify-between items-center shadow-md z-20">
        <div class="flex items-center gap-3.5">
            <div class="logo-font text-base font-black text-white tracking-widest bg-cyan-500/10 border border-cyan-500/20 px-3 py-1.5 rounded-xl text-cyan-400">ALAGÖZ</div>
            <div>
                <p class="text-xs text-white font-semibold">{{ current_user.username }}</p>
                <p class="text-[10px] text-slate-400 font-mono">ID: {{ current_user.custom_id }}</p>
            </div>
        </div>
        <div class="flex items-center gap-3">
            <span class="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-[11px] font-medium flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Sistem Çevrimiçi
            </span>
            <a href="/logout" class="bg-rose-500/10 text-rose-400 hover:bg-rose-500 hover:text-white px-3.5 py-2 rounded-xl text-xs font-medium transition border border-rose-500/20 flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"/></svg>
                Çıkış
            </a>
        </div>
    </header>

    <!-- Ana Panel -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        <!-- Sol Kenar Çubuğu (Kullanıcı Listesi) -->
        <aside class="w-full md:w-80 bg-[#0e1320] border-r border-slate-800 flex flex-col p-4 gap-3.5">
            <div class="relative">
                <input type="text" id="search-id-input" oninput="filterUsers()" placeholder="Kullanıcı veya ID ara..." class="w-full pl-9 pr-3.5 py-2.5 bg-[#0b0f19] border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition shadow-inner">
                <svg class="w-4 h-4 text-slate-500 absolute left-3 top-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
            </div>
            
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1 mt-1 flex justify-between items-center">
                <span>Aktif Üyeler</span>
                <span id="user-count" class="bg-slate-800 text-slate-300 px-2 py-0.5 rounded-md font-mono">0</span>
            </div>
            
            <div id="users-list" class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scroll">
                <p class="text-xs text-slate-500 text-center mt-6">Kullanıcılar yükleniyor...</p>
            </div>
        </aside>

        <!-- Sağ Alan (Sohbet) -->
        <section class="flex-1 flex flex-col bg-[#0b0f19] relative">
            <div id="chat-header" class="px-6 py-3.5 bg-[#131825] border-b border-slate-800 text-xs font-semibold text-slate-300 hidden flex justify-between items-center z-10">
                <span id="active-chat-title" class="flex items-center gap-2.5 text-white font-semibold">Sohbet Seçilmedi</span>
                <div class="flex items-center gap-3">
                    <button id="call-btn" onclick="toggleAudioCall()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/20 flex items-center gap-2 cursor-pointer">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                        Sesli Arama Başlat
                    </button>
                </div>
            </div>

            <!-- Ses Akış Elementi -->
            <audio id="remote-audio" autoplay playsinline></audio>

            <div id="chat-messages" class="flex-1 p-6 overflow-y-auto space-y-3.5 flex flex-col custom-scroll">
                <div class="m-auto text-center space-y-3 max-w-sm">
                    <div class="logo-font text-xl text-cyan-400 font-black tracking-widest">ALAGÖZ</div>
                    <p class="text-xs text-slate-400 font-medium leading-relaxed">Sol panelden bir kullanıcı seçerek güvenli mesajlaşmaya başlayın.</p>
                </div>
            </div>

            <form id="chat-form" onsubmit="sendPrivateMessage(event)" class="p-4 bg-[#131825] border-t border-slate-800 flex gap-3 hidden z-10">
                <input type="text" id="message-input" autocomplete="off" placeholder="Mesajınızı yazın..." class="flex-1 px-4 py-3 bg-[#0b0f19] border border-slate-800 rounded-xl text-xs focus:outline-none focus:border-cyan-500 text-white placeholder-slate-500 transition shadow-inner">
                <button type="submit" class="px-6 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-cyan-600/20 flex items-center gap-1.5 cursor-pointer">
                    Gönder
                    <svg class="w-3.5 h-3.5 rotate-90" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/></svg>
                </button>
            </form>
        </section>
    </div>

    <!-- AKTİF SESLİ GÖRÜŞME EKRANI (TAM EKRAN MODAL) -->
    <div id="active-call-screen" class="fixed inset-0 bg-[#0b0f19]/95 backdrop-blur-xl z-50 hidden flex flex-col items-center justify-center p-6 space-y-8">
        <div class="w-28 h-28 rounded-full bg-cyan-500/10 border-2 border-cyan-500/40 flex items-center justify-center text-cyan-400 text-4xl shadow-2xl animate-pulse">🎙️</div>
        <div class="text-center space-y-2">
            <h2 class="text-xl font-bold text-white" id="active-call-username">Kullanıcı</h2>
            <p class="text-xs text-emerald-400 font-mono tracking-wider">SESLİ BAĞLANTI AKTİF</p>
            <p class="text-sm text-slate-400 font-mono" id="call-timer">00:00</p>
        </div>
        <div class="flex items-center gap-6 pt-4">
            <button onclick="hangUp()" class="px-8 py-4 bg-rose-600 hover:bg-rose-500 text-white rounded-2xl text-sm font-bold shadow-xl shadow-rose-600/30 flex items-center gap-3 transition transform hover:scale-105 cursor-pointer">
                <svg class="w-5 h-5 rotate-135" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                Aramayı Sonlandır
            </button>
        </div>
    </div>

    <!-- GELEN ÇAĞRI MODALI -->
    <div id="incoming-call-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md z-50 hidden flex items-center justify-center p-4">
        <div class="bg-[#131825] border border-slate-800 p-8 rounded-3xl shadow-2xl w-full max-w-sm text-center space-y-6">
            <div class="w-20 h-20 rounded-full bg-cyan-500/10 border-2 border-cyan-500/40 flex items-center justify-center mx-auto text-cyan-400 text-2xl font-bold shadow-xl animate-bounce">📞</div>
            <div>
                <h2 class="text-base font-bold text-white" id="caller-name">Arayan Kişi</h2>
                <p class="text-xs text-cyan-400 font-mono mt-1">Gelen Sesli Çağrı...</p>
            </div>
            <div class="flex justify-center gap-8 pt-2">
                <button onclick="rejectCall()" class="w-14 h-14 rounded-full bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-600/40 transition transform hover:scale-105 cursor-pointer">
                    <svg class="w-6 h-6 rotate-135" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                </button>
                <button onclick="acceptCall()" class="w-14 h-14 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-600/40 transition transform hover:scale-105 cursor-pointer">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                </button>
            </div>
        </div>
    </div>

    <!-- WEBRTC & SOKET KONTROLÜ -->
    <script>
        const socket = io();
        const myId = "{{ current_user.custom_id }}";
        const myName = "{{ current_user.username }}";
        let targetId = null;
        let targetName = null;
        let localStream = null;
        let peerConnection = null;
        let inCall = false;
        let incomingCallerId = null;
        let globalUsers = [];
        let callTimerInterval = null;
        let callSeconds = 0;

        const iceServers = { 
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun.stunprotocol.org:3478' }
            ] 
        };

        socket.on('connect', () => {
            socket.emit('register_socket', { custom_id: myId });
        });

        function fetchUsers() {
            fetch('/get_users')
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    globalUsers = data.users;
                    document.getElementById('user-count').innerText = globalUsers.length;
                    renderUsers(globalUsers);
                }
            });
        }

        function renderUsers(users) {
            const listDiv = document.getElementById('users-list');
            const searchVal = document.getElementById('search-id-input').value.toLowerCase().trim();
            const filtered = users.filter(u => (u.username.toLowerCase().includes(searchVal) || u.custom_id.includes(searchVal)) && u.custom_id !== myId);

            if(filtered.length === 0) {
                listDiv.innerHTML = '<p class="text-xs text-slate-500 text-center mt-6">Kullanıcı bulunamadı.</p>';
                return;
            }
            listDiv.innerHTML = '';
            filtered.forEach(u => {
                const item = document.createElement('div');
                item.className = `p-3 rounded-xl border cursor-pointer transition flex items-center justify-between group ${targetId === u.custom_id ? 'bg-cyan-500/10 border-cyan-500/40' : 'bg-[#131825] border-slate-800 hover:bg-[#1a2233]'}`;
                item.onclick = () => startChat(u.custom_id, u.username, u.online);
                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="relative w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-200 text-xs">
                            ${u.username[0].toUpperCase()}
                            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[#0e1320] ${u.online ? 'bg-emerald-400' : 'bg-slate-600'}"></span>
                        </div>
                        <div>
                            <p class="text-xs font-semibold text-white group-hover:text-cyan-400 transition">${u.username}</p>
                            <p class="text-[10px] text-slate-400 font-mono">ID: ${u.custom_id}</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-slate-300 bg-[#0b0f19] px-2 py-1 rounded-lg border border-slate-800">Seç</span>
                `;
                listDiv.appendChild(item);
            });
        }

        function filterUsers() {
            renderUsers(globalUsers);
        }

        setInterval(fetchUsers, 3000);
        fetchUsers();

        function startChat(id, name, isOnline) {
            targetId = id;
            targetName = name;
            document.getElementById('active-chat-title').innerHTML = `💬 ${name} (ID: ${id}) — <span class="${isOnline ? 'text-emerald-400 font-medium' : 'text-slate-500'}">${isOnline ? '● Çevrimiçi' : '○ Çevrimdışı'}</span>`;
            document.getElementById('chat-header').classList.remove('hidden');
            document.getElementById('chat-form').classList.remove('hidden');
            document.getElementById('chat-messages').innerHTML = `<div class="text-center text-xs text-slate-500 my-2">-- ${name} ile güvenli kanal açıldı --</div>`;
            
            socket.emit('join_room_private', { user1: myId, user2: targetId });
            renderUsers(globalUsers);
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
            div.className = `flex flex-col ${isMe ? 'items-end' : 'items-start'} mb-2.5`;
            div.innerHTML = `
                <div class="px-4 py-2.5 rounded-2xl max-w-xs text-xs shadow-md ${isMe ? 'bg-cyan-600 text-white rounded-br-none' : 'bg-[#131825] border border-slate-800 text-slate-200 rounded-bl-none'}">
                    ${msg}
                </div>
            `;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // --- WEBRTC SES MOTORU & ÇAĞRI EKRANI ---
        function createPeerConnection() {
            if (peerConnection) return;
            peerConnection = new RTCPeerConnection(iceServers);

            if (localStream) {
                localStream.getTracks().forEach(track => {
                    peerConnection.addTrack(track, localStream);
                });
            }

            peerConnection.ontrack = event => {
                const remoteAudio = document.getElementById('remote-audio');
                if (event.streams && event.streams[0]) {
                    remoteAudio.srcObject = event.streams[0];
                    remoteAudio.play().catch(err => console.log("Ses oynatma hatası:", err));
                }
            };

            peerConnection.onicecandidate = event => {
                if (event.candidate && targetId) {
                    socket.emit('voice', { 
                        sender_id: myId, 
                        target_id: targetId, 
                        type: 'candidate', 
                        candidate: event.candidate 
                    });
                }
            };
        }

        function startCallTimer() {
            callSeconds = 0;
            document.getElementById('call-timer').innerText = "00:00";
            if(callTimerInterval) clearInterval(callTimerInterval);
            callTimerInterval = setInterval(() => {
                callSeconds++;
                let mins = Math.floor(callSeconds / 60).toString().padStart(2, '0');
                let secs = (callSeconds % 60).toString().padStart(2, '0');
                document.getElementById('call-timer').innerText = `${mins}:${secs}`;
            }, 1000);
        }

        async function toggleAudioCall() {
            if (!targetId) {
                alert("Önce bir kullanıcı seçmelisiniz!");
                return;
            }

            if(!inCall) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
                    inCall = true;
                    
                    document.getElementById('active-call-username').innerText = targetName || "Kullanıcı";
                    document.getElementById('active-call-screen').classList.remove('hidden');
                    startCallTimer();

                    createPeerConnection();

                    const offer = await peerConnection.createOffer();
                    await peerConnection.setLocalDescription(offer);

                    socket.emit('voice', { 
                        sender_id: myId, 
                        target_id: targetId, 
                        type: 'offer', 
                        sdp: offer 
                    });
                } catch(err) {
                    alert("Mikrofon izni alınamadı veya cihazda mikrofon bulunamadı!");
                    inCall = false;
                }
            } else {
                hangUp();
            }
        }

        socket.on('voice', async data => {
            if (data.type === 'offer') {
                incomingCallerId = data.sender_id;
                targetId = data.sender_id;
                window.pendingOffer = data.sdp;
                
                const callerObj = globalUsers.find(u => u.custom_id === data.sender_id);
                const callerDisplayName = callerObj ? callerObj.username : `ID: ${data.sender_id}`;
                targetName = callerDisplayName;
                
                document.getElementById('caller-name').innerText = callerDisplayName;
                document.getElementById('incoming-call-modal').classList.remove('hidden');
                
            } else if (data.type === 'answer' && peerConnection) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
                
            } else if (data.type === 'candidate' && peerConnection) {
                if (data.candidate) {
                    try {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                    } catch (e) {
                        console.log("ICE ekleme hatası:", e);
                    }
                }
            } else if (data.type === 'hangup') {
                resetCallState();
            }
        });

        async function acceptCall() {
            document.getElementById('incoming-call-modal').classList.add('hidden');
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
                inCall = true;
                
                document.getElementById('active-call-username').innerText = targetName || "Kullanıcı";
                document.getElementById('active-call-screen').classList.remove('hidden');
                startCallTimer();

                createPeerConnection();

                await peerConnection.setRemoteDescription(new RTCSessionDescription(window.pendingOffer));

                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);

                socket.emit('voice', { 
                    sender_id: myId, 
                    target_id: targetId, 
                    type: 'answer', 
                    sdp: answer 
                });
            } catch(e) {
                alert("Mikrofon izni alınamadı.");
                inCall = false;
            }
        }

        function rejectCall() {
            document.getElementById('incoming-call-modal').classList.add('hidden');
            if(incomingCallerId) {
                socket.emit('voice', { sender_id: myId, target_id: incomingCallerId, type: 'hangup' });
            }
            incomingCallerId = null;
        }

        function hangUp() {
            if(targetId) {
                socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'hangup' });
            }
            resetCallState();
        }

        function resetCallState() {
            if(localStream) {
                localStream.getTracks().forEach(t => t.stop());
            }
            if(peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            if(callTimerInterval) clearInterval(callTimerInterval);
            
            localStream = null;
            inCall = false;
            document.getElementById('incoming-call-modal').classList.add('hidden');
            document.getElementById('active-call-screen').classList.add('hidden');
        }
    </script>
</body>
</html>
"""

# --- BACKEND ROUTE & SOCKET MİMARİSİ ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat'))
        
        from flask import flash
        flash("Hatalı kullanıcı adı veya şifre!", "error")
        return render_template_string(AUTH_TEMPLATE), 401
    return render_template_string(AUTH_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            from flask import flash
            flash("Bu kullanıcı adı zaten alınmış!", "error")
            return render_template_string(AUTH_TEMPLATE), 400
        
        while True:
            custom_id = ''.join(random.choices(string.digits, k=6))
            if not User.query.filter_by(custom_id=custom_id).first():
                break
                
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw, custom_id=custom_id)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('chat'))
    return render_template_string(AUTH_TEMPLATE)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        new_password = request.form.get('new_password')
        
        user = User.query.filter_by(username=username).first()
        from flask import flash
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash("Şifreniz başarıyla güncellendi! Yeni şifrenizle giriş yapabilirsiniz.", "success")
            return redirect(url_for('login'))
        else:
            flash("Böyle bir kullanıcı adı bulunamadı!", "error")
            return render_template_string(AUTH_TEMPLATE), 404
            
    return render_template_string(AUTH_TEMPLATE)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/chat')
@login_required
def chat():
    return render_template_string(CHAT_TEMPLATE)

@app.route('/get_users')
@login_required
def get_users():
    users = User.query.all()
    user_list = []
    for u in users:
        user_list.append({
            'custom_id': u.custom_id,
            'username': u.username,
            'online': u.custom_id in active_sockets
        })
    return jsonify({'success': True, 'users': user_list})

@socketio.on('register_socket')
def handle_register(data):
    custom_id = data.get('custom_id')
    if custom_id:
        active_sockets[custom_id] = request.sid

@socketio.on('join_room_private')
def handle_join_private(data):
    u1 = data.get('user1')
    u2 = data.get('user2')
    room = "".join(sorted([u1, u2]))
    join_room(room)

@socketio.on('send_msg')
def handle_send_msg(data):
    receiver_id = data.get('receiver_id')
    if receiver_id in active_sockets:
        emit('receive_msg', data, room=active_sockets[receiver_id])

@socketio.on('voice')
def handle_voice(data):
    target_id = data.get('target_id')
    if target_id in active_sockets:
        emit('voice', data, room=active_sockets[target_id])

@socketio.on('disconnect')
def handle_disconnect():
    for cid, sid in list(active_sockets.items()):
        if sid == request.sid:
            del active_sockets[cid]
            break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
