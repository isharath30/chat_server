from flask import Flask, request
from flask_socketio import SocketIO, emit
import datetime
import sqlite3
import signal
import sys,os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

DB_FILE = os.path.join(os.path.dirname(__file__), 'server_log.db')
server_name = "Server A"
start_time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
daily_client_count = 0
monthly_client_count = 0
total_clients = 0
ratings = []
usernames = {}

def log_event(event_type, details):
    timestamp = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO logs (timestamp, event_type, details) VALUES (?, ?, ?)''', (timestamp, event_type, details))
    conn.commit()
    conn.close()
    if event_type != "shutdown":
        print(f"{details}")

def update_metrics(event, rating=None):
    global daily_client_count, monthly_client_count, total_clients, ratings
    if event == 'new_connection':
        daily_client_count += 1
        monthly_client_count += 1
        total_clients += 1
    elif event == 'rating' and rating is not None:
        ratings.append(rating)

@socketio.on('set_username')
def handle_set_username(data):
    username = data.get('username')
    sid = request.sid

    if username:
        usernames[sid] = username
        log_event('Connection', f"Accepted new connection from {username}")
        update_metrics('new_connection')
        emit('message', {'message': f"'{username}' has joined the chat."}, broadcast=True, include_self=False)

@socketio.on('message')
def handle_message(data):
    message_text = data['message']
    username = data.get('username')

    if message_text.lower() == 'exit':
        emit('request_rating', {'message': 'Please provide your rating before exiting.'}, broadcast=False)
    else:
        if username:
            log_event('Message', f"'{username}': {message_text}")
            emit('message', {'message': f"'{username}': {message_text}"}, broadcast=True, include_self=False)

@socketio.on('rating')
def handle_rating(data):
    rating = data['rating']
    username = data.get('username')

    if username:
        log_event('Rating', f'Received rating {rating} from {username}')
        update_metrics('rating', rating)
        emit('action', {'action': 'clear_inputs'})
        log_event('Disconnection', f'{username} has left the chat')
        emit('message', {'message': f'{username} has left the chat.'}, broadcast=True, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = usernames.pop(sid, None)
    if username:
        log_event('Disconnection', f'{username} has disconnected')
        emit('message', {'message': f'{username} has disconnected.'}, broadcast=True, include_self=False)

def shutdown_server(signum, frame):
    average_rating = sum(ratings) / len(ratings) if ratings else 0
    summary = (
        f"Server Name: {server_name}\n"
        f"Start Time: {start_time}\n"
        f"End Time: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
        f"Daily Client Count: {daily_client_count}\n"
        f"Monthly Client Count: {monthly_client_count}\n"
        f"Total Clients: {total_clients}\n"
        f"Average Rating: {average_rating:.2f}\n"
    )
    log_event('shutdown', f'Server shutting down...\n{summary}')
    print("\nServer shutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_server)
signal.signal(signal.SIGTERM, shutdown_server)

def setup_database():
    if not os.path.isfile(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()


if __name__ == "__main__":
    setup_database()
    print("Server started")
