from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz-interkom-guvenli-anahtar'
socketio = SocketIO(app, cors_allowed_origins="*")

connected_users = {} # {sid: username}
active_calls = {} 
call_history = [] 
private_messages = {} # {(user1, user2): [messages]}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ALAGÖZ - Profesyonel İletişim Sistemi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .glow-effect { box-shadow: 0 0 25px rgba(59, 130, 246, 0.15); }
        .call-glow { box-shadow: 0 0 60px rgba(16, 185, 129, 0.3); }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between p-5 select-none overflow-hidden">

    <!-- Giriş Ekranı -->
    <div id="login-screen" class="fixed inset-0 bg-slate-950/95 backdrop-blur-2xl z-50 flex items-center justify-center p-6">
        <div class="bg-slate-900/60 border border-slate-800/80 p-8 rounded-[2.5rem] shadow-2xl w-full max-w-sm text-center space-y-6 glow-effect">
            <div class="w-20 h-20 bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-blue-500/30 text-3xl font-black text-white tracking-tighter">A</div>
            <div>
                <h1 class="text-2xl font-extrabold tracking-tight text-white">ALAGÖZ</h1>
                <p class="text-slate-400 text-xs mt-1 font-medium tracking-wide uppercase">Profesyonel İletişim Sistemi</p>
            </div>
            <div class="space-y-3">
                <input type="text" id="username-input" placeholder="Konum / Oda (Örn: Salon, Mutfak)" class="w-full px-4 py-4 bg-slate-950/80 border border-slate-800/80 rounded-2xl focus:outline-none focus:border-blue-500 text-center text-sm text-white placeholder-slate-600 font-medium transition">
                <button onclick="registerUser()" class="w-full py-4 bg-blue-600 hover:bg-blue-500 active:scale-95 font-bold text-sm rounded-2xl transition shadow-lg shadow-blue-600/30 text-white">Sisteme Bağlan</button>
            </div>
        </div>
    </div>

    <!-- Gelen Çağrı Modal Ekranı -->
    <div id="incoming-call-modal" class="fixed inset-0 bg-slate-950/90 backdrop-blur-xl z-50 hidden flex items-center justify-center p-6">
        <div class="bg-slate-900 border border-slate-800 p-8 rounded-[2.5rem] shadow-2xl w-full max-w-sm text-center space-y-6 animate-pulse">
            <div class="w-20 h-20 bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 rounded-full flex items-center justify-center mx-auto text-4xl">📞</div>
            <div>
                <h2 class="text-xl font-bold text-white">Gelen Sesli Arama</h2>
                <p id="caller-name-text" class="text-blue-400 text-sm font-semibold mt-1">Biri sizi arıyor...</p>
            </div>
            <div class="grid grid-cols-2 gap-3 pt-2">
                <button onclick="rejectCall()" class="py-3.5 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/30 text-rose-400 font-bold rounded-2xl transition active:scale-95">Reddet</button>
                <button onclick="acceptCall()" class="py-3.5 bg-emerald-600 hover:bg-emerald-500 font-bold text-white rounded-2xl transition shadow-lg shadow-emerald-600/30 active:scale-95">Kabul Et</button>
            </div>
        </div>
    </div>

    <!-- Arama Yapılıyor (Çalıyor...) Ekranı -->
    <div id="outgoing-call-modal" class="fixed inset-0 bg-slate-950/90 backdrop-blur-xl z-50 hidden flex items-center justify-center p-6">
        <div class="bg-slate-900 border border-slate-800 p-8 rounded-[2.5rem] shadow-2xl w-full max-w-sm text-center space-y-6">
            <div class="w-20 h-20 bg-blue-600/20 border border-blue-500/30 text-blue-400 rounded-full flex items-center justify-center mx-auto text-4xl animate-spin">📡</div>
            <div>
                <h2 class="text-xl font-bold text-white">Aranıyor</h2>
                <p id="outgoing-target-text" class="text-slate-400 text-sm font-semibold mt-1">Bağlantı kuruluyor...</p>
            </div>
            <button onclick="cancelOutgoingCall()" class="w-full py-3.5 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/30 text-rose-400 font-bold rounded-2xl transition active:scale-95">İptal Et</button>
        </div>
    </div>

    <!-- Ekran Üstü Anlık Mesaj Bildirim Banner'ı -->
    <div id="floating-notification" onclick="openChatFromNotification()" class="fixed top-5 left-1/2 -translate-x-1/2 bg-slate-900/95 border border-blue-500/40 px-5 py-3 rounded-2xl shadow-2xl z-50 hidden cursor-pointer transition-all duration-300 flex items-center space-x-3 backdrop-blur-xl">
        <div class="w-10 h-10 bg-blue-600/20 text-blue-400 rounded-xl flex items-center justify-center text-lg font-bold">💬</div>
        <div>
            <h4 id="notif-sender" class="text-xs font-bold text-white">Yeni Mesaj</h4>
            <p id="notif-text" class="text-[11px] text-slate-400 font-medium truncate max-w-[200px]">Mesaj içeriği...</p>
        </div>
    </div>

    <!-- Arayüz İçi Şık Uyarı Modal'ı -->
    <div id="system-alert-modal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex items-center justify-center p-6">
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-[2rem] shadow-2xl w-full max-w-xs text-center space-y-4">
            <div id="alert-icon" class="w-14 h-14 bg-rose-600/20 border border-rose-500/30 text-rose-400 rounded-2xl flex items-center justify-center mx-auto text-2xl">⚠️</div>
            <div>
                <h3 id="alert-title" class="text-base font-bold text-white">Durum Bildirimi</h3>
                <p id="alert-message" class="text-slate-400 text-xs mt-1 font-medium">Açıklama metni...</p>
            </div>
            <button onclick="closeSystemAlert()" class="w-full py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs rounded-xl transition">Tamam</button>
        </div>
    </div>

    <!-- Üst Header -->
    <header class="flex items-center justify-between bg-slate-900/40 border border-slate-800/60 p-4 rounded-2xl backdrop-blur-xl">
        <div class="flex items-center space-x-3">
            <div class="w-9 h-9 bg-blue-600/10 border border-blue-500/20 rounded-xl flex items-center justify-center text-blue-400 font-black text-sm">A</div>
            <div>
                <span class="text-[9px] text-slate-500 uppercase tracking-widest font-bold block">Aktif İstasyon</span>
                <h2 id="my-name-display" class="font-bold text-xs text-blue-400">-</h2>
            </div>
        </div>
        <div class="flex items-center space-x-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
            <span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
            <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-wider">Çevrimiçi</span>
        </div>
    </header>

    <!-- Sekmeler Paneli -->
    <main class="flex-1 my-4 flex flex-col space-y-3 overflow-hidden">
        <div class="flex bg-slate-900/60 p-1 rounded-xl border border-slate-800">
            <button onclick="switchTab('devices')" id="tab-devices-btn" class="flex-1 py-2 text-[11px] font-bold rounded-lg bg-blue-600 text-white transition shadow">Birimler</button>
            <button onclick="switchTab('history')" id="tab-history-btn" class="flex-1 py-2 text-[11px] font-bold rounded-lg text-slate-400 hover:text-white transition">Geçmiş</button>
        </div>

        <!-- 1. Birimler Sekmesi -->
        <div id="section-devices" class="flex-1 flex flex-col space-y-2 overflow-hidden">
            <div class="flex items-center justify-between px-1">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Kanalda Bekleyen Diğer Birimler</h3>
                <span id="device-count" class="text-[10px] bg-slate-900 text-slate-400 px-2 py-0.5 rounded-md font-semibold">0 Bağlı</span>
            </div>
            <div id="users-list" class="flex-1 overflow-y-auto space-y-2 pr-1">
                <div class="p-6 bg-slate-900/30 border border-slate-900/80 rounded-2xl text-center text-slate-600 text-xs font-medium">Ağ taranıyor...</div>
            </div>
        </div>

        <!-- 2. Özel Sohbet Ekranı -->
        <div id="section-chat" class="flex-1 flex flex-col space-y-2 overflow-hidden hidden">
            <div class="flex items-center justify-between px-3 py-2 bg-slate-900/60 border border-slate-800/80 rounded-2xl">
                <div class="flex items-center space-x-2.5">
                    <button onclick="closeChat()" class="text-slate-400 hover:text-white text-base font-bold px-1">←</button>
                    <div>
                        <h3 id="chat-target-name" class="text-xs font-bold text-white">Sohbet</h3>
                        <span class="text-[9px] text-emerald-400 font-semibold">● Özel Kanal</span>
                    </div>
                </div>
            </div>
            <!-- Mesaj Akışı -->
            <div id="chat-messages-box" class="flex-1 bg-slate-900/40 border border-slate-800/80 rounded-2xl p-3 overflow-y-auto space-y-3 text-xs">
                <div class="text-center text-slate-600 text-[11px] py-4">Mesajlar yükleniyor...</div>
            </div>
            <!-- Mesaj Girişi -->
            <div class="flex space-x-2 pt-1">
                <input type="text" id="chat-input" placeholder="Özel mesaj yazın..." onkeypress="handleChatKey(event)" class="flex-1 px-4 py-3 bg-slate-900/80 border border-slate-800 rounded-xl focus:outline-none focus:border-blue-500 text-xs text-white placeholder-slate-500">
                <button onclick="sendPrivateMessage()" class="px-5 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl transition shadow-lg shadow-blue-600/20 active:scale-95">Gönder</button>
            </div>
        </div>

        <!-- 3. Arama Geçmişi Sekmesi -->
        <div id="section-history" class="flex-1 flex flex-col space-y-2 overflow-hidden hidden">
            <div class="flex items-center justify-between px-1">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Son Sesli Görüşmeler</h3>
            </div>
            <div id="history-list" class="flex-1 overflow-y-auto space-y-2 pr-1">
                <div class="p-6 bg-slate-900/30 border border-slate-900/80 rounded-2xl text-center text-slate-600 text-xs font-medium">Henüz geçmiş kayıt yok.</div>
            </div>
        </div>
    </main>

    <footer class="text-center py-2">
        <p class="text-[10px] text-slate-600 font-semibold tracking-wider">ALAGÖZ SECURE AUDIO PROTOCOL</p>
    </footer>

    <!-- Aktif Normal Arama Ekranı (Ahize Modu) -->
    <div id="call-active-screen" class="fixed inset-0 bg-slate-950/98 backdrop-blur-3xl z-50 hidden flex flex-col justify-between p-6">
        <div class="flex items-center justify-between border-b border-slate-900 pb-4">
            <div class="flex items-center space-x-2">
                <span class="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-ping"></span>
                <span class="text-xs text-emerald-400 font-extrabold uppercase tracking-widest">Ahize Görüşmesi Aktif</span>
            </div>
            <div class="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 text-[11px] font-bold flex items-center space-x-1.5">
                <span>📞</span>
                <span>Ahize</span>
            </div>
        </div>

        <div class="text-center space-y-6 my-auto">
            <div class="w-36 h-36 bg-slate-900/80 border border-slate-800/80 rounded-full flex items-center justify-center mx-auto text-5xl shadow-2xl relative call-glow">
                <span>🎧</span>
            </div>
            <div class="space-y-1">
                <h2 id="active-peer-name" class="text-2xl font-black text-white tracking-tight">Bağlantı Kuruldu</h2>
                <p class="text-emerald-400 text-xs font-semibold">Ahize ses kanalı açık (Dinliyor & Konuşuyorsunuz)</p>
            </div>
        </div>

        <div class="flex flex-col items-center space-y-3 pb-4">
            <button onclick="endActiveCall()" class="w-full max-w-xs py-4 bg-rose-600 hover:bg-rose-500 active:scale-95 rounded-2xl font-bold shadow-lg shadow-rose-600/30 transition-all flex items-center justify-center space-x-2 text-white text-sm">
                <span class="text-lg">📴</span>
                <span>Görüşmeyi Sonlandır</span>
            </button>
            <span class="text-[11px] text-slate-500 font-medium">Hattı güvenle kapatmak için dokun</span>
        </div>
    </div>

    <!-- Uzaktan ses oynatmak için ses elementi (Ahize Çıkışı) -->
    <audio id="remote-audio" autoplay playsinline></audio>

    <script>
        let socket;
        let myUsername = "";
        let activeTargetId = "";
        let activeChatTargetName = "";
        let incomingCallerId = "";
        let outgoingTargetId = "";
        let localStream = null;
        let audioCtx = null;
        let ringtoneInterval = null;
        let notifTimeout = null;
        let lastNotifSender = "";

        function initAudioContext() {
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
        }

        function playTone(freq1, freq2, type, duration) {
            try {
                initAudioContext();
                if(audioCtx.state === 'suspended') audioCtx.resume();
                
                const osc1 = audioCtx.createOscillator();
                const osc2 = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                
                osc1.type = type;
                osc1.frequency.value = freq1;
                osc2.type = type;
                osc2.frequency.value = freq2;
                
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
                
                osc1.connect(gain);
                osc2.connect(gain);
                gain.connect(audioCtx.destination);
                
                osc1.start();
                osc2.start();
                osc1.stop(audioCtx.currentTime + duration);
                osc2.stop(audioCtx.currentTime + duration);
            } catch(e) {}
        }

        function playBeep() { playTone(580, 750, 'sine', 0.1); }
        function playSuccessSound() { playTone(880, 1100, 'sine', 0.25); }
        function playRejectSound() { playTone(300, 200, 'sawtooth', 0.35); }
        function playMsgNotificationTone() { playTone(750, 950, 'sine', 0.18); }
        
        function startRingtone() {
            stopRingtone();
            playTone(440, 480, 'sine', 1.2);
            ringtoneInterval = setInterval(() => {
                playTone(440, 480, 'sine', 1.2);
            }, 2500);
        }

        function stopRingtone() {
            if(ringtoneInterval) {
                clearInterval(ringtoneInterval);
                ringtoneInterval = null;
            }
        }

        function showSystemAlert(title, message, isError = true) {
            document.getElementById('alert-title').innerText = title;
            document.getElementById('alert-message').innerText = message;
            const iconEl = document.getElementById('alert-icon');
            if(isError) {
                iconEl.className = "w-14 h-14 bg-rose-600/20 border border-rose-500/30 text-rose-400 rounded-2xl flex items-center justify-center mx-auto text-2xl";
                iconEl.innerText = "⚠️";
                playRejectSound();
            } else {
                iconEl.className = "w-14 h-14 bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto text-2xl";
                iconEl.innerText = "ℹ️";
                playSuccessSound();
            }
            document.getElementById('system-alert-modal').classList.remove('hidden');
        }

        function closeSystemAlert() {
            document.getElementById('system-alert-modal').classList.add('hidden');
        }

        function switchTab(tab) {
            playBeep();
            const devBtn = document.getElementById('tab-devices-btn');
            const histBtn = document.getElementById('tab-history-btn');
            const devSec = document.getElementById('section-devices');
            const chatSec = document.getElementById('section-chat');
            const histSec = document.getElementById('section-history');

            devBtn.className = "flex-1 py-2 text-[11px] font-bold rounded-lg text-slate-400 hover:text-white transition";
            histBtn.className = "flex-1 py-2 text-[11px] font-bold rounded-lg text-slate-400 hover:text-white transition";

            devSec.classList.add('hidden');
            chatSec.classList.add('hidden');
            histSec.classList.add('hidden');

            if(tab === 'devices') {
                devBtn.className = "flex-1 py-2 text-[11px] font-bold rounded-lg bg-blue-600 text-white transition shadow";
                devSec.classList.remove('hidden');
            } else {
                histBtn.className = "flex-1 py-2 text-[11px] font-bold rounded-lg bg-blue-600 text-white transition shadow";
                histSec.classList.remove('hidden');
                socket.emit('get_history');
            }
        }

        function openChatWith(name) {
            playBeep();
            activeChatTargetName = name;
            document.getElementById('chat-target-name').innerText = name + " ile Sohbet";
            
            document.getElementById('section-devices').classList.add('hidden');
            document.getElementById('section-history').classList.add('hidden');
            document.getElementById('section-chat').classList.remove('hidden');
            
            socket.emit('get_private_history', { target: name });
        }

        function closeChat() {
            playBeep();
            activeChatTargetName = "";
            document.getElementById('section-chat').classList.add('hidden');
            document.getElementById('section-devices').classList.remove('hidden');
        }

        function openChatFromNotification() {
            if(lastNotifSender) {
                openChatWith(lastNotifSender);
            }
            document.getElementById('floating-notification').classList.add('hidden');
        }

        function showFloatingNotification(sender, text) {
            lastNotifSender = sender;
            document.getElementById('notif-sender').innerText = sender + " yeni mesaj gönderdi";
            document.getElementById('notif-text').innerText = text;
            
            const banner = document.getElementById('floating-notification');
            banner.classList.remove('hidden');
            playMsgNotificationTone();

            if(notifTimeout) clearTimeout(notifTimeout);
            notifTimeout = setTimeout(() => {
                banner.classList.add('hidden');
            }, 4000);
        }

        async function registerUser() {
            const input = document.getElementById('username-input').value.trim();
            if(!input) return alert("Lütfen bir konum veya isim gir!");
            myUsername = input;
            document.getElementById('my-name-display').innerText = myUsername;
            document.getElementById('login-screen').classList.add('hidden');
            initAudioContext();

            try {
                localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
            } catch (e) {
                alert("Mikrofon izni alınamadı! Lütfen tarayıcı izinlerini kontrol edin.");
            }

            socket = io();

            socket.on('connect', () => {
                socket.emit('register', { username: myUsername });
            });

            socket.on('update_users', (users) => {
                const listEl = document.getElementById('users-list');
                listEl.innerHTML = '';
                
                const otherUsers = Object.keys(users).filter(id => users[id] !== myUsername);
                document.getElementById('device-count').innerText = otherUsers.length + " Bağlı";
                
                if(otherUsers.length === 0) {
                    listEl.innerHTML = '<div class="p-6 bg-slate-900/30 border border-slate-900/80 rounded-2xl text-center text-slate-600 text-xs font-medium">Ağda başka aktif birim yok...</div>';
                    return;
                }

                otherUsers.forEach(id => {
                    const name = users[id];
                    const div = document.createElement('div');
                    div.className = "flex items-center justify-between p-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl shadow-lg backdrop-blur-md";
                    div.innerHTML = `
                        <div onclick="openChatWith('${name}')" class="flex items-center space-x-3.5 flex-1 cursor-pointer">
                            <div class="w-11 h-11 bg-blue-600/10 border border-blue-500/20 rounded-xl flex items-center justify-center text-blue-400 font-bold text-lg">💬</div>
                            <div>
                                <span class="font-bold text-sm text-slate-200 block">${name}</span>
                                <span class="text-[10px] text-emerald-400 font-semibold flex items-center gap-1 mt-0.5">● Sohbet Et & Ara</span>
                            </div>
                        </div>
                        <button onclick="callUser('${id}', '${name}')" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 font-extrabold text-xs rounded-xl transition shadow-lg shadow-blue-600/25 text-white active:scale-95">Ara</button>
                    `;
                    listEl.appendChild(div);
                });
            });

            socket.on('incoming_call', (data) => {
                incomingCallerId = data.callerId;
                document.getElementById('caller-name-text').innerText = data.callerName + " sizi arıyor...";
                document.getElementById('incoming-call-modal').classList.remove('hidden');
                startRingtone();
            });

            socket.on('call_accepted', (data) => {
                stopRingtone();
                document.getElementById('outgoing-call-modal').classList.add('hidden');
                document.getElementById('incoming-call-modal').classList.add('hidden');
                activeTargetId = data.targetId;
                document.getElementById('active-peer-name').innerText = data.targetName;
                document.getElementById('call-active-screen').classList.remove('hidden');
                playSuccessSound();
            });

            socket.on('call_rejected', (data) => {
                stopRingtone();
                document.getElementById('outgoing-call-modal').classList.add('hidden');
                document.getElementById('incoming-call-modal').classList.add('hidden');
                document.getElementById('call-active-screen').classList.add('hidden');
                activeTargetId = "";
                showSystemAlert("Arama Bildirimi", data.reason || "Arama sonlandırıldı.", true);
            });

            socket.on('history_data', (history) => {
                const histList = document.getElementById('history-list');
                histList.innerHTML = '';
                if(history.length === 0) {
                    histList.innerHTML = '<div class="p-6 bg-slate-900/30 border border-slate-900/80 rounded-2xl text-center text-slate-600 text-xs font-medium">Henüz geçmiş kayıt yok.</div>';
                    return;
                }
                history.reverse().forEach(item => {
                    const div = document.createElement('div');
                    div.className = "flex items-center justify-between p-3.5 bg-slate-900/60 border border-slate-800/80 rounded-2xl shadow-md";
                    div.innerHTML = `
                        <div class="flex items-center space-x-3">
                            <div class="w-9 h-9 bg-slate-800 text-emerald-400 rounded-xl flex items-center justify-center font-bold text-sm">📞</div>
                            <div>
                                <span class="font-bold text-xs text-slate-200 block">${item.caller} ➔ ${item.target}</span>
                                <span class="text-[9px] text-slate-500 font-medium">${item.time}</span>
                            </div>
                        </div>
                        <span class="px-2 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] font-bold rounded-md">Görüştü</span>
                    `;
                    histList.appendChild(div);
                });
            });

            socket.on('private_history', (messages) => {
                renderChatMessages(messages);
            });

            socket.on('new_private_message', (msg) => {
                if (activeChatTargetName === msg.sender) {
                    appendChatMessage(msg);
                    playMsgNotificationTone();
                    socket.emit('mark_read', { sender: msg.sender });
                } else {
                    showFloatingNotification(msg.sender, msg.text);
                }
            });

            socket.on('messages_read_update', () => {
                const chatBox = document.getElementById('chat-messages-box');
                chatBox.querySelectorAll('.seen-indicator').forEach(el => el.innerText = '✔✔ Görüldü');
            });

            socket.on('audio_stream', (data) => {
                const audio = document.getElementById('remote-audio');
                audio.src = "data:audio/webm;base64," + data.audio;
                audio.play().catch(e => {});
            });
        }

        function callUser(id, name) {
            playBeep();
            outgoingTargetId = id;
            document.getElementById('outgoing-target-text').innerText = name + " aranıyor...";
            document.getElementById('outgoing-call-modal').classList.remove('hidden');
            startRingtone();
            socket.emit('call_request', { target: id, callerName: myUsername });
        }

        function cancelOutgoingCall() {
            stopRingtone();
            document.getElementById('outgoing-call-modal').classList.add('hidden');
            socket.emit('end_call', { target: outgoingTargetId });
            outgoingTargetId = "";
        }

        function acceptCall() {
            stopRingtone();
            document.getElementById('incoming-call-modal').classList.add('hidden');
            socket.emit('accept_call', { callerId: incomingCallerId });
        }

        function rejectCall() {
            stopRingtone();
            document.getElementById('incoming-call-modal').classList.add('hidden');
            socket.emit('reject_call', { callerId: incomingCallerId });
            incomingCallerId = "";
        }

        function endActiveCall() {
            playRejectSound();
            document.getElementById('call-active-screen').classList.add('hidden');
            socket.emit('end_call', { target: activeTargetId });
            activeTargetId = "";
        }

        function sendPrivateMessage() {
            const inputEl = document.getElementById('chat-input');
            const text = inputEl.value.trim();
            if(!text || !activeChatTargetName) return;
            
            socket.emit('send_private_message', { target: activeChatTargetName, text: text });
            inputEl.value = '';
        }

        function handleChatKey(e) {
            if(e.key === 'Enter') sendPrivateMessage();
        }

        function renderChatMessages(messages) {
            const box = document.getElementById('chat-messages-box');
            box.innerHTML = '';
            if(messages.length === 0) {
                box.innerHTML = '<div class="text-center text-slate-600 text-[11px] py-4">Henüz mesaj yok. İlk mesajı sen yaz!</div>';
                return;
            }
            messages.forEach(msg => appendChatMessage(msg));
        }

        function appendChatMessage(msg) {
            const box = document.getElementById('chat-messages-box');
            if(box.querySelector('.text-slate-600')) box.innerHTML = '';
            
            const isMe = msg.sender === myUsername;
            const div = document.createElement('div');
            div.className = `flex flex-col ${isMe ? 'items-end' : 'items-start'}`;
            
            let statusText = '';
            if (isMe) {
                statusText = `<span class="text-[9px] text-blue-400 font-semibold seen-indicator">${msg.read ? '✔✔ Görüldü' : '✔ İletildi'}</span>`;
            }

            div.innerHTML = `
                <div class="flex items-center space-x-1.5 mb-1 px-1">
                    <span class="font-bold text-[10px] text-slate-400">${msg.sender}</span>
                    <span class="text-[9px] text-slate-600">${msg.time}</span>
                </div>
                <div class="max-w-[85%] px-3.5 py-2.5 rounded-2xl text-xs font-medium shadow-md ${isMe ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700/50'}">
                    ${msg.text}
                </div>
                <div class="mt-0.5 px-1">${statusText}</div>
            `;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        setInterval(() => {
            if (!activeTargetId || !localStream) return;
            
            const mediaRecorder = new MediaRecorder(localStream, { mimeType: 'audio/webm' });
            let chunks = [];
            
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
            mediaRecorder.onstop = () => {
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = () => {
                    const base64 = reader.result.split(',')[1];
                    if (activeTargetId && base64) {
                        socket.emit('audio_stream', { target: activeTargetId, audio: base64 });
                    }
                };
            };
            
            mediaRecorder.start();
            setTimeout(() => {
                if (mediaRecorder.state === "recording") mediaRecorder.stop();
            }, 300);
        }, 350);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('register')
def handle_register(data):
    connected_users[request.sid] = data['username']
    socketio.emit('update_users', connected_users)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in connected_users:
        del connected_users[request.sid]
    if request.sid in active_calls:
        peer = active_calls[request.sid]
        if peer in active_calls:
            del active_calls[peer]
        del active_calls[request.sid]
        socketio.emit('call_rejected', {'reason': 'Karşı taraf hattan ayrıldı.'}, room=peer)
    socketio.emit('update_users', connected_users)

@socketio.on('call_request')
def handle_call_request(data):
    target = data['target']
    caller_name = data['callerName']
    
    if target in active_calls or any(v == target for v in active_calls.values()):
        emit('call_rejected', {'reason': 'Aradığınız kişi şu an başka bir hatla görüşmede (Meşgul).'})
        return

    socketio.emit('incoming_call', {'callerId': request.sid, 'callerName': caller_name}, room=target)

@socketio.on('accept_call')
def handle_accept_call(data):
    caller_id = data['callerId']
    acceptor_name = connected_users.get(request.sid, 'Biri')
    caller_name = connected_users.get(caller_id, 'Biri')
    
    active_calls[request.sid] = caller_id
    active_calls[caller_id] = request.sid
    
    call_history.append({
        'caller': caller_name,
        'target': acceptor_name,
        'time': datetime.now().strftime('%H:%M - %d.%m.%Y')
    })
    
    socketio.emit('call_accepted', {'targetId': request.sid, 'targetName': acceptor_name}, room=caller_id)
    socketio.emit('call_accepted', {'targetId': caller_id, 'targetName': caller_name}, room=request.sid)

@socketio.on('reject_call')
def handle_reject_call(data):
    caller_id = data['callerId']
    socketio.emit('call_rejected', {'reason': 'Karşı taraf çağrıyı reddetti.'}, room=caller_id)

@socketio.on('end_call')
def handle_end_call(data):
    target = data.get('target')
    if request.sid in active_calls:
        peer = active_calls[request.sid]
        if peer in active_calls:
            del active_calls[peer]
        del active_calls[request.sid]
        socketio.emit('call_rejected', {'reason': 'Karşı taraf hattı kapattı.'}, room=peer)
    if target and target in active_calls:
        peer = active_calls[target]
        if peer in active_calls:
            del active_calls[peer]
        del active_calls[target]
        socketio.emit('call_rejected', {'reason': 'Karşı taraf hattı kapattı.'}, room=target)

@socketio.on('get_history')
def handle_get_history():
    socketio.emit('history_data', call_history, room=request.sid)

@socketio.on('get_private_history')
def handle_get_private_history(data):
    my_name = connected_users.get(request.sid)
    target_name = data['target']
    
    key = tuple(sorted([my_name, target_name]))
    messages = private_messages.get(key, [])
    
    for m in messages:
        if m['sender'] != my_name:
            m['read'] = True
            
    socketio.emit('private_history', messages, room=request.sid)
    
    for sid, uname in connected_users.items():
        if uname == target_name:
            socketio.emit('messages_read_update', room=sid)

@socketio.on('mark_read')
def handle_mark_read(data):
    my_name = connected_users.get(request.sid)
    sender_name = data['sender']
    key = tuple(sorted([my_name, sender_name]))
    if key in private_messages:
        for m in private_messages[key]:
            if m['sender'] != my_name:
                m['read'] = True
                
    for sid, uname in connected_users.items():
        if uname == sender_name:
            socketio.emit('messages_read_update', room=sid)

@socketio.on('send_private_message')
def handle_send_private_message(data):
    sender = connected_users.get(request.sid, 'Bilinmeyen')
    target_name = data['target']
    
    key = tuple(sorted([sender, target_name]))
    if key not in private_messages:
        private_messages[key] = []
        
    msg = {
        'sender': sender,
        'target': target_name,
        'text': data['text'],
        'time': datetime.now().strftime('%H:%M'),
        'read': False
    }
    private_messages[key].append(msg)
    
    socketio.emit('private_history', private_messages[key], room=request.sid)
    
    for sid, uname in connected_users.items():
        if uname == target_name:
            socketio.emit('new_private_message', msg, room=sid)

@socketio.on('audio_stream')
def handle_audio_stream(data):
    target = data['target']
    audio_data = data['audio']
    socketio.emit('audio_stream', {'audio': audio_data}, room=target)

if __name__ == '__main__':
    # Render'ın vereceği port numarasını otomatik alması için:
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)