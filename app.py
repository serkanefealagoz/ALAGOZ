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

# Aktif Soket Bağlantıları Hafızası
active_sockets = {}

# --- GİRİŞ / KAYIT / ŞİFREYİ UNUTTUM ORTAK ŞABLON (FÜTÜRİSTİK MAVİ-BEYAZ DENGELİ) ---
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
<body class="bg-[#121c33] text-slate-100 h-screen flex items-center justify-center overflow-hidden relative selection:bg-blue-500 selection:text-white">
    <!-- Dengeli Arka Plan Efekti -->
    <div class="absolute -top-32 -left-32 w-96 h-96 bg-blue-600/15 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-32 -right-32 w-96 h-96 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-md p-8 bg-[#1a2642]/90 backdrop-blur-xl border border-blue-500/30 rounded-3xl shadow-2xl relative z-10 mx-4">
        
        <!-- Fütüristik Kurumsal ALAGÖZ Logosu -->
        <div class="text-center mb-8">
            <h1 class="logo-font text-2xl font-black bg-gradient-to-r from-white via-blue-200 to-blue-400 bg-clip-text text-transparent drop-shadow-md">ALAGÖZ</h1>
            <p class="text-xs text-blue-200/70 font-medium tracking-wide mt-1">
                {% if request.path == '/login' %} Güvenli Oturum Paneli
                {% elif request.path == '/register' %} Yeni Hesap Oluşturma Merkezi
                {% else %} Şifre Kurtarma Modülü {% endif %}
            </p>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="mb-5 p-3.5 {% if category == 'success' %}bg-emerald-500/20 border-emerald-500/40 text-emerald-300{% else %}bg-rose-500/20 border-rose-500/40 text-rose-300{% endif %} border text-xs rounded-xl text-center font-medium shadow-sm">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-[11px] font-bold text-blue-200 uppercase tracking-wider mb-1.5">Kullanıcı Adı</label>
                <input type="text" name="username" required autocomplete="off" class="w-full px-4 py-3.5 bg-[#121c33] border border-blue-500/40 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 transition shadow-inner">
            </div>

            {% if request.path != '/forgot-password' %}
            <div>
                <label class="block text-[11px] font-bold text-blue-200 uppercase tracking-wider mb-1.5">Şifre</label>
                <input type="password" name="password" required class="w-full px-4 py-3.5 bg-[#121c33] border border-blue-500/40 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 transition shadow-inner">
            </div>
            {% else %}
            <div>
                <label class="block text-[11px] font-bold text-blue-200 uppercase tracking-wider mb-1.5">Yeni Şifre Belirle</label>
                <input type="password" name="new_password" required class="w-full px-4 py-3.5 bg-[#121c33] border border-blue-500/40 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 transition shadow-inner">
            </div>
            {% endif %}

            <button type="submit" class="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-blue-600/30 cursor-pointer mt-2 border border-blue-400/30">
                {% if request.path == '/login' %} Sisteme Giriş Yap
                {% elif request.path == '/register' %} Hesabı Hemen Oluştur
                {% else %} Şifreyi Güncelle ve Sıfırla {% endif %}
            </button>
        </form>

        <!-- Ekstra Bağlantılar (Şifremi Unuttum & Ekran Değiştirme) -->
        <div class="mt-6 pt-4 border-t border-blue-500/20 text-center space-y-2.5">
            {% if request.path == '/login' %}
                <p class="text-xs text-slate-300">Şifrenizi mi unuttunuz? <a href="/forgot-password" class="text-blue-300 font-bold hover:underline">Şifreyi Sıfırla</a></p>
                <p class="text-xs text-slate-300">Hesabınız yok mu? <a href="/register" class="text-white font-bold underline hover:text-blue-300">Kayıt Ol Ekranına Git</a></p>
            {% elif request.path == '/register' %}
                <p class="text-xs text-slate-300">Zaten hesabınız var mı? <a href="/login" class="text-white font-bold underline hover:text-blue-300">Normal Giriş Yap</a></p>
            {% else %}
                <p class="text-xs text-slate-300">Şifrenizi hatırladınız mı? <a href="/login" class="text-blue-300 font-bold hover:underline">Giriş Ekranına Dön</a></p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# --- CHAT ARAYÜZÜ (KURUMSAL MAVİ-BEYAZ & KESİN ÇÖZÜMLÜ SES MOTORU) ---
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ — Kurumsal İletişim Ağı</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .logo-font { font-family: 'Orbitron', sans-serif; letter-spacing: 1.5px; }
        .custom-scroll::-webkit-scrollbar { width: 5px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #3b82f640; border-radius: 10px; }
    </style>
</head>
<body class="bg-[#121c33] text-slate-100 h-screen flex flex-col overflow-hidden selection:bg-blue-500 selection:text-white">
    
    <!-- Üst Kurumsal Bar -->
    <header class="bg-[#1a2642] border-b border-blue-500/20 px-6 py-3.5 flex justify-between items-center shadow-lg z-20">
        <div class="flex items-center gap-3.5">
            <div class="logo-font text-lg font-black text-white tracking-widest bg-blue-600/30 px-3 py-1.5 rounded-xl border border-blue-400/30">ALAGÖZ</div>
            <div>
                <p class="text-xs text-white font-semibold">{{ current_user.username }}</p>
                <p class="text-[10px] text-blue-200/70 font-mono">ID: {{ current_user.custom_id }}</p>
            </div>
        </div>
        <div class="flex items-center gap-3">
            <span class="px-3 py-1.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-xl text-[11px] font-medium flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Sistem Aktif
            </span>
            <a href="/logout" class="bg-rose-500/15 text-rose-300 hover:bg-rose-500 hover:text-white px-3.5 py-2 rounded-xl text-xs font-medium transition border border-rose-500/30 flex items-center gap-1.5 shadow-sm">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"/></svg>
                Çıkış
            </a>
        </div>
    </header>

    <!-- Ana Panel -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        <!-- Sol Kenar Çubuğu (Kullanıcı Listesi) -->
        <aside class="w-full md:w-80 bg-[#16213b] border-r border-blue-500/20 flex flex-col p-4 gap-3.5">
            <div class="relative">
                <input type="text" id="search-id-input" oninput="filterUsers()" placeholder="Kullanıcı veya ID ara..." class="w-full pl-9 pr-3.5 py-2.5 bg-[#121c33] border border-blue-500/30 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 transition shadow-inner">
                <svg class="w-4 h-4 text-blue-300/60 absolute left-3 top-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
            </div>
            
            <div class="text-[10px] font-bold text-blue-200 uppercase tracking-wider px-1 mt-1 flex justify-between items-center">
                <span>Çevrimiçi Üyeler</span>
                <span id="user-count" class="bg-blue-600/30 text-blue-200 px-2 py-0.5 rounded-md font-mono">0</span>
            </div>
            
            <div id="users-list" class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scroll">
                <p class="text-xs text-slate-400 text-center mt-6">Kullanıcılar yükleniyor...</p>
            </div>
        </aside>

        <!-- Sağ Alan (Sohbet ve Sesli Görüşme) -->
        <section class="flex-1 flex flex-col bg-[#121c33] relative">
            <div id="chat-header" class="px-6 py-3.5 bg-[#1a2642]/80 backdrop-blur-md border-b border-blue-500/20 text-xs font-semibold text-white hidden flex justify-between items-center z-10">
                <span id="active-chat-title" class="flex items-center gap-2.5 text-white font-semibold">Sohbet Seçilmedi</span>
                <div class="flex items-center gap-3">
                    <span id="call-status-badge" class="hidden px-3 py-1 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-xl text-[11px] font-mono animate-pulse">Ses Bağlantısı Kuruldu</span>
                    <button id="call-btn" onclick="toggleAudioCall()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/25 flex items-center gap-2 cursor-pointer border border-emerald-400/30">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                        Sesli Arama
                    </button>
                </div>
            </div>

            <!-- Ses Çalma Elementi -->
            <audio id="remote-audio" autoplay playsinline></audio>

            <div id="chat-messages" class="flex-1 p-6 overflow-y-auto space-y-3.5 flex flex-col custom-scroll">
                <div class="m-auto text-center space-y-3 max-w-sm">
                    <div class="logo-font text-xl text-blue-300 font-black tracking-widest">ALAGÖZ</div>
                    <p class="text-xs text-slate-300 font-medium leading-relaxed">Sol panelden bir kullanıcı seçerek güvenli şifreli mesajlaşmaya veya sesli görüşmeye başlayın.</p>
                </div>
            </div>

            <form id="chat-form" onsubmit="sendPrivateMessage(event)" class="p-4 bg-[#1a2642]/80 backdrop-blur-md border-t border-blue-500/20 flex gap-3 hidden z-10">
                <input type="text" id="message-input" autocomplete="off" placeholder="Mesajınızı şifreli olarak gönderin..." class="flex-1 px-4 py-3 bg-[#121c33] border border-blue-500/30 rounded-xl text-xs focus:outline-none focus:border-blue-400 text-white placeholder-slate-400 transition shadow-inner">
                <button type="submit" class="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-blue-600/25 flex items-center gap-1.5 cursor-pointer border border-blue-400/30">
                    Gönder
                    <svg class="w-3.5 h-3.5 rotate-90" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/></svg>
                </button>
            </form>
        </section>
    </div>

    <!-- GELEN ARAMA MODALI -->
    <div id="incoming-call-modal" class="fixed inset-0 bg-black/80 backdrop-blur-md z-50 hidden flex items-center justify-center p-4">
        <div class="bg-[#1a2642] border border-blue-500/40 p-8 rounded-3xl shadow-2xl w-full max-w-sm text-center space-y-6">
            <div class="w-20 h-20 rounded-full bg-blue-600/20 border-2 border-blue-400/50 flex items-center justify-center mx-auto text-blue-300 text-2xl font-bold shadow-xl shadow-blue-600/30 animate-pulse">📞</div>
            <div>
                <h2 class="text-base font-bold text-white" id="caller-name">Arayan Kişi</h2>
                <p class="text-xs text-blue-300 font-mono mt-1">Gelen Şifreli Sesli Çağrı...</p>
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

    <!-- KESİN ÇÖZÜMLÜ WEBRTC SES MOTORU -->
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
                listDiv.innerHTML = '<p class="text-xs text-slate-400 text-center mt-6">Başka kullanıcı bulunamadı.</p>';
                return;
            }
            listDiv.innerHTML = '';
            filtered.forEach(u => {
                const item = document.createElement('div');
                item.className = `p-3 rounded-xl border cursor-pointer transition flex items-center justify-between group ${targetId === u.custom_id ? 'bg-blue-600/20 border-blue-400/50' : 'bg-[#121c33] border-blue-500/20 hover:bg-[#1a2642]'}`;
                item.onclick = () => startChat(u.custom_id, u.username, u.online);
                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="relative w-9 h-9 rounded-xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center font-bold text-blue-200 text-xs">
                            ${u.username[0].toUpperCase()}
                            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[#16213b] ${u.online ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
                        </div>
                        <div>
                            <p class="text-xs font-semibold text-white group-hover:text-blue-300 transition">${u.username}</p>
                            <p class="text-[10px] text-blue-200/60 font-mono">ID: ${u.custom_id}</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-blue-200 bg-[#121c33] px-2 py-1 rounded-lg border border-blue-500/30">Seç</span>
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
            document.getElementById('active-chat-title').innerHTML = `💬 ${name} (ID: ${id}) — <span class="${isOnline ? 'text-emerald-400 font-medium' : 'text-slate-400'}">${isOnline ? '● Çevrimiçi' : '○ Çevrimdışı'}</span>`;
            document.getElementById('chat-header').classList.remove('hidden');
            document.getElementById('chat-form').classList.remove('hidden');
            document.getElementById('chat-messages').innerHTML = `<div class="text-center text-xs text-blue-200/60 my-2">-- ${name} ile güvenli kanal açıldı --</div>`;
            
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
                <div class="px-4 py-2.5 rounded-2xl max-w-xs text-xs shadow-md ${isMe ? 'bg-blue-600 text-white rounded-br-none border border-blue-400/30' : 'bg-[#1a2642] border border-blue-500/30 text-white rounded-bl-none'}">
                    ${msg}
                </div>
            `;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // --- WEBRTC SES KÖPRÜSÜ (KESİN ÇÖZÜM) ---
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
                    remoteAudio.play().catch(err => console.log("Ses oynatma tetikleme hatası:", err));
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

        async function toggleAudioCall() {
            if (!targetId) {
                alert("Önce bir kullanıcı seçmelisiniz!");
                return;
            }
            const btn = document.getElementById('call-btn');
            const badge = document.getElementById('call-status-badge');

            if(!inCall) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
                    inCall = true;
                    
                    btn.className = "px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-rose-600/25 flex items-center gap-2 cursor-pointer border border-rose-400/30";
                    btn.innerHTML = "🔴 Aramayı Kapat";
                    badge.classList.remove('hidden');

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
                    alert("Mikrofon izni reddedildi veya cihazınızda mikrofon bulunamadı!");
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
                
                document.getElementById('caller-name').innerText = callerDisplayName;
                document.getElementById('incoming-call-modal').classList.remove('hidden');
                
            } else if (data.type === 'answer' && peerConnection) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
                
            } else if (data.type === 'candidate' && peerConnection) {
                if (data.candidate) {
                    try {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                    } catch (e) {
                        console.log("ICE aday ekleme hatası:", e);
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
                
                const btn = document.getElementById('call-btn');
                const badge = document.getElementById('call-status-badge');
                btn.className = "px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-rose-600/25 flex items-center gap-2 cursor-pointer border border-rose-400/30";
                btn.innerHTML = "🔴 Aramayı Kapat";
                badge.classList.remove('hidden');

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
            localStream = null;
            inCall = false;
            document.getElementById('incoming-call-modal').classList.add('hidden');
            document.getElementById('call-status-badge').classList.add('hidden');
            
            const btn = document.getElementById('call-btn');
            if(btn) {
                btn.className = "px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/25 flex items-center gap-2 cursor-pointer border border-emerald-400/30";
                btn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                    Sesli Arama
                `;
            }
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

# --- SOCKET.IO HABERLEŞME VE SES KÖPRÜSÜ ---

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
