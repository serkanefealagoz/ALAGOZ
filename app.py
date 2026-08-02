from flask import Flask, render_template, redirect, url_for, request, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz-profesyonel-gizli-anahtar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Aktif/Online kullanıcıları takip etmek için sözlük (sid -> user_id)
online_users = {}

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
            return redirect(url_for('chat'))
        else:
            flash('Kimlik Numarası veya Şifre hatalı!', 'danger')
            
    return render_template('login.html')

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
        
        flash(f'Kayıt başarılı! Size özel Kimlik Numaranız: {generated_id}', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', current_user=current_user)

@app.route('/get_all_users', methods=['GET'])
@login_required
def get_all_users():
    users = User.query.all()
    user_list = []
    for u in users:
        if u.custom_id != current_user.custom_id:
            # Online durumunu kontrol et
            is_online = u.custom_id in online_users.values()
            user_list.append({
                'custom_id': u.custom_id,
                'username': u.username,
                'online': is_online
            })
    return {'success': True, 'users': user_list}

@app.route('/search_user', methods=['GET'])
@login_required
def search_user():
    query_id = request.args.get('id', '').strip()
    user = User.query.filter_by(custom_id=query_id).first()
    if user and user.custom_id != current_user.custom_id:
        is_online = user.custom_id in online_users.values()
        return {'success': True, 'username': user.username, 'custom_id': user.custom_id, 'online': is_online}
    return {'success': False, 'message': 'Bu ID ye ait kullanıcı bulunamadı.'}

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- WEBSOCKET & SES / MESAJ MANTIĞI ---
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        online_users[request.sid] = current_user.custom_id
        socketio.emit('update_status', {'custom_id': current_user.custom_id, 'online': True})

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in online_users:
        uid = online_users[sid]
        del online_users[sid]
        socketio.emit('update_status', {'custom_id': uid, 'online': False})

@socketio.on('join_private_room')
def on_join(data):
    room = ''.join(sorted([str(data['user1']), str(data['user2'])]))
    join_room(room)

@socketio.on('send_private_message')
def handle_private_message(data):
    room = ''.join(sorted([str(data['sender_id']), str(data['receiver_id'])]))
    emit('receive_private_message', {
        'sender_id': data['sender_id'],
        'sender_name': data['sender_name'],
        'msg': data['msg']
    }, room=room)

# Sesli arama WebRTC sinyalleşmesi (Sesin düzgün akması için)
@socketio.on('voice_signal')
def handle_voice_signal(data):
    room = ''.join(sorted([str(data['sender_id']), str(data['target_id'])]))
    emit('voice_signal', data, room=room, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
