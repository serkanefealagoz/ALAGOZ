from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template_string, redirect, url_for, request, flash
from flask_socketio import SocketIO, emit, join_room, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz-enterprise-security-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Aktif socket oturumlarını ve eşleşen custom_id'leri takip eden güvenli sözlük
active_sessions = {}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# --- PROFESYONEL ÖN YÜZ (CHAT_TEMPLATE) ---
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALAGÖZ — Kurumsal Güvenli İletişim</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .custom-scroll::-webkit-scrollbar { width: 5px; }
        .custom-scroll::-webkit-scrollbar-track { background: transparent; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
    </style>
</head>
<body class="bg-[#070b14] text-slate-100 h-screen flex flex-col overflow-hidden selection:bg-indigo-500 selection:text-white">
    
    <!-- Üst Kurumsal Bar -->
    <header class="bg-[#0b1322] border-b border-slate-800/80 px-6 py-3.5 flex justify-between items-center shadow-2xl z-20">
        <div class="flex items-center gap-3.5">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-600/30 text-base">A</div>
            <div>
                <h1 class="text-xs font-bold tracking-wider text-indigo-400 uppercase">ALAGÖZ SECURE NETWORK</h1>
                <p class="text-xs text-slate-400">{{ current_user.username }} • <span class="text-emerald-400 font-mono text-[11px]">ID: {{ current_user.custom_id }}</span></p>
            </div>
        </div>
        <a href="/logout" class="bg-rose-500/10 text-rose-400 hover:bg-rose-500 hover:text-white px-4 py-2 rounded-xl text-xs font-medium transition border border-rose-500/20 flex items-center gap-2 shadow-sm">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"/></svg>
            Oturumu Kapat
        </a>
    </header>

    <!-- Ana Panel -->
    <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        <!-- Sol Kenar Çubuğu: Rehber & Arama -->
        <aside class="w-full md:w-80 bg-[#090f1d] border-r border-slate-800/80 flex flex-col p-4 gap-3.5">
            <div class="relative">
                <input type="text" id="search-id-input" oninput="filterUsers()" placeholder="ID veya Rumuz ile ara..." class="w-full pl-9 pr-3.5 py-2.5 bg-[#070b14] border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition shadow-inner">
                <svg class="w-4 h-4 text-slate-500 absolute left-3 top-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
            </div>
            
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-1 mt-1 flex justify-between items-center">
                <span>Sistemdeki Üyeler</span>
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            
            <div id="users-list" class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scroll">
                <p class="text-xs text-slate-500 text-center mt-6">Kullanıcılar yükleniyor...</p>
            </div>
        </aside>

        <!-- Sağ Alan: Sohbet Penceresi -->
        <section class="flex-1 flex flex-col bg-[#070b14] relative">
            <div id="chat-header" class="px-6 py-3.5 bg-[#0b1322]/60 border-b border-slate-800/80 text-xs font-semibold text-slate-300 hidden flex justify-between items-center z-10">
                <span id="active-chat-title" class="flex items-center gap-2 text-slate-200">Sohbet Seçilmedi</span>
                <button id="call-btn" onclick="startAudioCall()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/20 flex items-center gap-2 cursor-pointer">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/></svg>
                    Sesli Arama
                </button>
            </div>

            <!-- Ses Akışı İçin Gizli Element -->
            <audio id="remote-audio" autoplay></audio>

            <div id="chat-messages" class="flex-1 p-6 overflow-y-auto space-y-3 flex flex-col custom-scroll">
                <div class="m-auto text-center space-y-3 max-w-sm">
                    <div class="w-16 h-16 rounded-2xl bg-[#0b1322] border border-slate-800 flex items-center justify-center mx-auto text-2xl shadow-xl">💬</div>
                    <p class="text-xs text-slate-400 font-medium">Sol listeden bir kişi seçerek şifreli mesajlaşmaya veya sesli görüşmeye başlayın.</p>
                </div>
            </div>

            <form id="chat-form" onsubmit="sendPrivateMessage(event)" class="p-4 bg-[#0b1322]/60 border-t border-slate-800/80 flex gap-3 hidden z-10">
                <input type="text" id="message-input" autocomplete="off" placeholder="Mesajınızı yazın..." class="flex-1 px-4 py-3 bg-[#070b14] border border-slate-800 rounded-xl text-xs focus:outline-none focus:border-indigo-500 text-slate-200 transition shadow-inner">
                <button type="submit" class="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-indigo-600/25 flex items-center gap-1.5 cursor-pointer">
                    Gönder
                    <svg class="w-3.5 h-3.5 rotate-90" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/></svg>
                </button>
            </form>
        </section>
    </div>

    <!-- GERÇEK TELEFON ÇAĞRI EKRANI (POP-UP MODAL) -->
    <div id="incoming-call-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md z-50 hidden flex items-center justify-center p-4">
        <div class="bg-[#0b1322] border border-slate-800 p-8 rounded-3xl shadow-2xl w-full max-w-sm text-center space-y-6">
            <div class="w-20 h-20 rounded-full bg-indigo-600/20 border-2 border-indigo-500/50 flex items-center justify-center mx-auto text-indigo-400 text-2xl font-bold shadow-xl shadow-indigo-600/20 animate-pulse">📞</div>
            <div>
                <h2 class="text-base font-bold text-slate-100" id="caller-name">Arayan Kişi</h2>
                <p class="text-xs text-indigo-400 font-mono mt-1">Gelen Şifreli Sesli Çağrı...</p>
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

    <!-- JAVASCRIPT HABERLEŞME VE WEBRTC ÇEKİRDEĞİ -->
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

        // Güçlendirilmiş STUN Sunucu Havuzu
        const iceServers = { 
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' }
            ] 
        };

        socket.on('connect', () => {
            console.log("Socket aktif. ID bildiriliyor:", myId);
            socket.emit('register_socket', { custom_id: myId });
        });

        function fetchUsers() {
            fetch('/get_users')
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    globalUsers = data.users;
                    renderUsers(globalUsers);
                }
            });
        }

        function renderUsers(users) {
            const listDiv = document.getElementById('users-list');
            const searchVal = document.getElementById('search-id-input').value.toLowerCase().trim();
            
            const filtered = users.filter(u => u.username.toLowerCase().includes(searchVal) || u.custom_id.includes(searchVal));

            if(filtered.length === 0) {
                listDiv.innerHTML = '<p class="text-xs text-slate-500 text-center mt-6">Kullanıcı bulunamadı.</p>';
                return;
            }
            listDiv.innerHTML = '';
            filtered.forEach(u => {
                const item = document.createElement('div');
                item.className = "p-3 rounded-xl bg-[#0b1322]/50 border border-slate-800/60 cursor-pointer hover:bg-[#151f33] transition flex items-center justify-between group";
                item.onclick = () => startChat(u.custom_id, u.username, u.online);
                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="relative w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center font-bold text-indigo-400 text-xs">
                            ${u.username[0].toUpperCase()}
                            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[#070b14] ${u.online ? 'bg-emerald-500' : 'bg-slate-600'}"></span>
                        </div>
                        <div>
                            <p class="text-xs font-semibold text-slate-200 group-hover:text-indigo-400 transition">${u.username}</p>
                            <p class="text-[10px] text-slate-400 font-mono">ID: ${u.custom_id}</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-slate-400 bg-[#070b14] px-2 py-1 rounded-lg border border-slate-800">Seç</span>
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
            document.getElementById('active-chat-title').innerHTML = `💬 ${name} (ID: ${id}) — <span class="${isOnline ? 'text-emerald-400' : 'text-slate-400'}">${isOnline ? '● Çevrimiçi' : '○ Çevrimdışı'}</span>`;
            document.getElementById('chat-header').classList.remove('hidden');
            document.getElementById('chat-form').classList.remove('hidden');
            document.getElementById('chat-messages').innerHTML = `<div class="text-center text-xs text-slate-500 my-2">-- ${name} ile güvenli hat kuruldu --</div>`;
            
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
                <div class="px-4 py-2.5 rounded-2xl max-w-xs text-xs shadow-md ${isMe ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-[#0b1322] border border-slate-800 text-slate-200 rounded-bl-none'}">
                    ${msg}
                </div>
            `;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // --- WEB-RTC SESLİ ARAMA SİSTEMİ ---
        async function startAudioCall() {
            if (!targetId) {
                alert("Önce bir kullanıcı seçmelisiniz!");
                return;
            }
            const btn = document.getElementById('call-btn');
            if(!inCall) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    inCall = true;
                    btn.className = "px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-rose-600/20 flex items-center gap-2 cursor-pointer";
                    btn.innerHTML = "🔴 Aramayı Kapat";
                    
                    setupPeer();
                    const offer = await peerConnection.createOffer();
                    await peerConnection.setLocalDescription(offer);
                    socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'offer', sdp: offer });
                } catch(err) {
                    alert("Mikrofon erişim izni reddedildi!");
                }
            } else {
                hangUp();
            }
        }

        function setupPeer() {
            if (peerConnection) return;
            peerConnection = new RTCPeerConnection(iceServers);

            if (localStream) {
                localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
            }
            
            peerConnection.ontrack = e => {
                const remoteAudio = document.getElementById('remote-audio');
                remoteAudio.srcObject = e.streams[0];
                remoteAudio.play().catch(err => console.log("Ses oynatma hatası:", err));
            };
            
            peerConnection.onicecandidate = e => {
                if(e.candidate && targetId) {
                    socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'candidate', candidate: e.candidate });
                }
            };
        }

        socket.on('voice', async data => {
            if(data.type === 'offer') {
                incomingCallerId = data.sender_id;
                const callerObj = globalUsers.find(u => u.custom_id === data.sender_id);
                const callerDisplayName = callerObj ? callerObj.username : `ID: ${data.sender_id}`;
                
                document.getElementById('caller-name').innerText = callerDisplayName;
                document.getElementById('incoming-call-modal').classList.remove('hidden');
                window.pendingOffer = data.sdp;
                targetId = data.sender_id;
            } else if(data.type === 'answer' && peerConnection) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
            } else if(data.type === 'candidate' && peerConnection) {
                try {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                } catch(e) {}
            } else if(data.type === 'hangup') {
                resetCallState();
            }
        });

        async function acceptCall() {
            document.getElementById('incoming-call-modal').classList.add('hidden');
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                inCall = true;
                const btn = document.getElementById('call-btn');
                btn.className = "px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-rose-600/20 flex items-center gap-2 cursor-pointer";
                btn.innerHTML = "🔴 Aramayı Kapat";

                setupPeer();
                await peerConnection.setRemoteDescription(new RTCSessionDescription(window.pendingOffer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'answer', sdp: answer });
            } catch(e) {
                alert("Mikrofon izni alınamadı.");
            }
        }

        function rejectCall() {
            document.getElementById('incoming-call-modal').classList.add('hidden');
            socket.emit('voice', { sender_id: myId, target_id: incomingCallerId, type: 'hangup' });
            incomingCallerId = null;
        }

        function hangUp() {
            if(targetId) {
                socket.emit('voice', { sender_id: myId, target_id: targetId, type: 'hangup' });
            }
            resetCallState();
        }

        function resetCallState() {
            if(localStream) localStream.getTracks().forEach(t => t.stop());
            if(peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            localStream = null;
            inCall = false;
            document.getElementById('incoming-call-modal').classList.add('hidden');
            const btn = document.getElementById('call-btn');
            if(btn) {
                btn.className = "px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/20 flex items-center gap-2 cursor-pointer";
                btn.innerHTML = "Sesli Arama";
            }
        }
    </script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş Yap — ALAGÖZ</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-[#070b14] text-slate-100 flex items-center justify-center h-screen px-4 selection:bg-indigo-500 selection:text-white">
    <div class="bg-[#0b1322] border border-slate-800/80 p-8 rounded-3xl shadow-2xl w-full max-w-md backdrop-blur-xl">
        <div class="text-center mb-8">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center font-bold text-white shadow-xl shadow-indigo-600/30 text-xl mx-auto mb-3">A</div>
            <h1 class="text-xl font-bold tracking-tight text-slate-100">ALAGÖZ PLATFORMU</h1>
            <p class="text-xs text-slate-400 mt-1">Devam etmek için giriş yapın</p>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="mb-5 p-3 text-xs rounded-xl bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-center font-medium">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Kullanıcı Adı</label>
                <input type="text" name="username" required placeholder="Kullanıcı adınızı girin" class="w-full px-4 py-3 rounded-xl bg-[#070b14] border border-slate-800 focus:outline-none focus:border-indigo-500 text-xs text-slate-200 transition shadow-inner">
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Şifre</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full px-4 py-3 rounded-xl bg-[#070b14] border border-slate-800 focus:outline-none focus:border-indigo-500 text-xs text-slate-200 transition shadow-inner">
            </div>
            <button type="submit" class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-semibold text-xs transition shadow-lg shadow-indigo-600/30 mt-2 cursor-pointer">Giriş Yap</button>
        </form>
        <p class="mt-6 text-center text-xs text-slate-400">Hesabınız yok mu? <a href="/register" class="text-indigo-400 hover:underline font-semibold">Kayıt Olun</a></p>
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
    <title>Kayıt Ol — ALAGÖZ</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-[#070b14] text-slate-100 flex items-center justify-center h-screen px-4 selection:bg-indigo-500 selection:text-white">
    <div class="bg-[#0b1322] border border-slate-800/80 p-8 rounded-3xl shadow-2xl w-full max-w-md backdrop-blur-xl">
        <div class="text-center mb-8">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center font-bold text-white shadow-xl shadow-emerald-600/30 text-xl mx-auto mb-3">A</div>
            <h1 class="text-xl font-bold tracking-tight text-slate-100">YENİ HESAP</h1>
            <p class="text-xs text-slate-400 mt-1">Güvenli ağa katılmak için kayıt olun</p>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="mb-5 p-3 text-xs rounded-xl bg-rose-500/10 text-rose-300 border border-rose-500/20 text-center font-medium">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Kullanıcı Adı / Rumuz</label>
                <input type="text" name="username" required placeholder="Örn: metin_alagoz" class="w-full px-4 py-3 rounded-xl bg-[#070b14] border border-slate-800 focus:outline-none focus:border-indigo-500 text-xs text-slate-200 transition shadow-inner">
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Şifre</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full px-4 py-3 rounded-xl bg-[#070b14] border border-slate-800 focus:outline-none focus:border-indigo-500 text-xs text-slate-200 transition shadow-inner">
            </div>
            <button type="submit" class="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-semibold text-xs transition shadow-lg shadow-emerald-600/30 mt-2 cursor-pointer">Kayıt Ol ve ID Al</button>
        </form>
        <p class="mt-6 text-center text-xs text-slate-400">Zaten hesabınız var mı? <a href="/login" class="text-indigo-400 hover:underline font-semibold">Giriş Yapın</a></p>
    </div>
</body>
</html>
"""

# --- BACKEND ROTARLARI ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Bu kullanıcı adı zaten alınmış! Lütfen başka bir kullanıcı adı seçin.', 'danger')
            return render_template_string(REGISTER_TEMPLATE)
        
        generated_id = str(random.randint(100000, 999999))
        while User.query.filter_by(custom_id=generated_id).first():
            generated_id = str(random.randint(100000, 999999))
            
        hashed_password = generate_password_hash(password)
        new_user = User(custom_id=generated_id, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Kayıt Başarılı! Otomatik ID Numaranız: {generated_id}. Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/chat')
@login_required
def chat():
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
                'online': u.custom_id in active_sessions.values()
            })
    return {'success': True, 'users': result}

@app.route('/logout')
@login_required
def logout():
    # Socket oturumlarını temizle
    sid_to_remove = [sid for sid, cid in active_sessions.items() if cid == current_user.custom_id]
    for sid in sid_to_remove:
        active_sessions.pop(sid, None)
    logout_user()
    return redirect(url_for('login'))

# --- SOCKET.IO KANALLARI ---

@socketio.on('register_socket')
def handle_register_socket(data):
    custom_id = data.get('custom_id')
    if custom_id:
        active_sessions[request.sid] = custom_id

@socketio.on('disconnect')
def handle_disconnect():
    active_sessions.pop(request.sid, None)

def get_room_name(id1, id2):
    return '_'.join(sorted([str(id1), str(id2)]))

@socketio.on('join_room_private')
def on_join(data):
    room = get_room_name(data['user1'], data['user2'])
    join_room(room)

@socketio.on('send_msg')
def handle_msg(data):
    room = get_room_name(data['sender_id'], data['receiver_id'])
    emit('receive_msg', {
        'sender_id': data['sender_id'],
        'sender_name': data['sender_name'],
        'msg': data['msg']
    }, room=room)

@socketio.on('voice')
def handle_voice(data):
    room = get_room_name(data['sender_id'], data['target_id'])
    emit('voice', data, room=room, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
