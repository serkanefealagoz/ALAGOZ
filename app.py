from flask import Flask, render_template, redirect, url_for, request, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alagoz-whatsapp-gizli-anahtar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Her kullanıcıya 6 haneli benzersiz bir WhatsApp tarzı kimlik numarası (ID) veriyoruz
    custom_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(150), nullable=False)

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
        custom_id = request.form.get('custom_id')
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
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Otomatik rastgele 6 haneli bir Kimlik Numarası üretelim (Örn: 482910)
        generated_id = str(random.randint(100000, 999999))
        while User.query.filter_by(custom_id=generated_id).first():
            generated_id = str(random.randint(100000, 999999))
            
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(custom_id=generated_id, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        # Kayıt olunca kimlik numarasını ekranda gösterelim ki bilsin
        flash(f'Kayıt başarılı! Size özel Kimlik Numaranız: {generated_id} (Giriş için bunu kullanın)', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', current_user=current_user)

# --- BİREBİR (1-to-1) WHATSAPP MANTIĞI SOCKET.IO ---
@socketio.on('join_private_room')
def on_join(data):
    # İki kullanıcı arasında ortak ve eşsiz bir oda adı yaratıyoruz (ID'leri sıralayıp birleştirerek)
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

@socketio.on('audio_stream')
def handle_audio(data):
    room = ''.join(sorted([str(data['sender_id']), str(data['target_id'])]))
    emit('audio_stream', data['audio'], room=room, include_self=False)

# Kullanıcı arama rotası (Kimlik numarasına göre arama)
@app.route('/search_user', methods=['GET'])
@login_required
def search_user():
    query_id = request.args.get('id')
    user = User.query.filter_by(custom_id=query_id).first()
    if user and user.custom_id != current_user.custom_id:
        return {'success': True, 'username': user.username, 'custom_id': user.custom_id}
    return {'success': False, 'message': 'Kullanıcı bulunamadı.'}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
