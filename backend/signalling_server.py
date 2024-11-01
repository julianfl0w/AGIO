from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import constants
from flask import request

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

connections = {}

import multiprocessing as mp
import brain


@socketio.on('connect', namespace='/connect')
def handle_connect():
    emit('candidates', json.dumps(connections))
    print("Client connected to /connect")

@socketio.on('disconnect', namespace='/connect')
def handle_disconnect():
    sid = request.sid  # Access the session ID of the disconnected client
    print(f"Client disconnected from /connect with session ID {sid}")
    connections.pop(sid, None)  # Remove the candidate associated with the disconnected session

@socketio.on('offer', namespace='/connect')
def handle_message(message):
    print(f"Received brain connect offer")

    offer = json.loads(message)

    host_id = offer.get('host_id')
    sdp = offer.get('sdp')

    if not host_id or not sdp:
        emit('failure', 'host_id and sdp required')
        return

    connections[request.sid] = json.loads(message)
    emit('success', 'Candidate saved successfully')

@socketio.on('answer', namespace='/connect')
def handle_answer(answer):
    print(f"Received answer")
    answer = json.loads(answer)

    # Placeholder for updating the peer connection with the answer
    # This typically involves fetching the peer connection object for the given client
    # and setting the answer on it.
    print("-----------------")
    host_sid = answer['host_sid']
    print(host_sid)
    # Fetch the peer connection object for the given client
    # This is a placeholder, replace with your actual logic to get the peer connection
    peer_connection = connections.get(host_sid)

    if peer_connection:
        print("Forwarding answer")
        emit('answer', json.dumps(answer), to=host_sid, namespace='/connect')

        # Signal back to the client who sent the answer if needed
        emit('status', json.dumps({'status': 'success', 'message': 'Answer processed successfully'}))
    else:
        print("Error: no peer connection")
        emit('status', json.dumps({'status': 'failed', 'message': 'Peer connection not found'}), to=host_sid, namespace='/connect')

if __name__ == '__main__':
    # Create a new process targeting brain.main
    #process = mp.Process(target=brain.main)
    # Start the process
    #process.start()

    socketio.run(app, debug=False, port=5000) 


