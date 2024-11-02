import uuid
import json
import asyncio
import dataclasses
import numpy as np
import fractions
import socketio

from aiortc import (
    RTCPeerConnection, 
    RTCSessionDescription,
    MediaStreamTrack
)
from aiortc.mediastreams import AudioStreamTrack
from av import AudioFrame

class SineWaveAudioStreamTrack(AudioStreamTrack):
    """
    An audio track that generates a sine wave.
    """
    def __init__(self):
        super().__init__()
        self.sample_rate = 48000  # Audio sample rate
        self.channels = 1  # Mono audio
        self.frequency = 440  # Frequency of the sine wave (A4 note)
        self.time = 0  # Keep track of time for sine wave generation
        self.pts = 0

    async def recv(self):
        """
        Generates a frame containing a sine wave.
        """
        samples = 1024  # Number of audio samples per frame
        t = np.linspace(self.time, self.time + samples / self.sample_rate, samples, False)
        audio_data = (np.sin(2 * np.pi * self.frequency * t) * 32767).astype(np.int16)
        frame = AudioFrame.from_ndarray(audio_data.reshape(self.channels, -1), format='s16p', layout='mono')
        frame.pts = self.pts
        frame.sample_rate = self.sample_rate
        frame.time_base = fractions.Fraction(1, self.sample_rate)
        self.pts += samples
        self.time += samples / self.sample_rate
        return frame

class RTCNode:
    def __init__(self):
        self.connections = {}
        mac_num = uuid.getnode()
        self.host_id = ':'.join(('%012X' % mac_num)[i:i+2] for i in range(0, 12, 2))
        self.server_url = "http://localhost:5000"
        self.room_id = "audio_room"  # Specify the room for all clients
        self.sio = socketio.AsyncClient()

    async def handle_status(self, message):
        print("Received status:", message)

    async def handle_answer(self, message):
        print("Received answer")
        answer_json = json.loads(message)
        client_id = answer_json.get("client_id")
        if client_id and client_id in self.connections:
            answer_sdp = RTCSessionDescription(**{k: v for k, v in answer_json.items() if k != 'client_id'})
            await self.connections[client_id].setRemoteDescription(answer_sdp)

    async def handle_disconnect(self):
        print("Received SIO disconnect")
        await self.sio.disconnect()
        for pc in self.connections.values():
            await pc.close()
        self.connections.clear()

    async def handleIce(self, client_id, event):
        if event.candidate:
            candidate_dict = dataclasses.asdict(event.candidate)
            await self.sio.emit('ice_candidate', json.dumps({
                'candidate': candidate_dict, 
                'client_id': client_id,
                'room_id': self.room_id
            }), namespace='/connect')

    async def sendOffer(self, client_id):
        pc = RTCPeerConnection()
        audio_track = SineWaveAudioStreamTrack()
        pc.addTrack(audio_track)
        self.connections[client_id] = pc

        # Handle ICE candidates
        @pc.on("icecandidate")
        async def on_ice_candidate(event):
            await self.handleIce(client_id, event)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await self.sio.emit('offer', json.dumps({
            'sdp': pc.localDescription.sdp, 
            'type': pc.localDescription.type, 
            'client_id': client_id, 
            'room_id': self.room_id
        }), namespace='/connect')

    async def sendAnswerAndConnect(self, remote_sid, candidate):
        pc = RTCPeerConnection()
        client_id = remote_sid

        # Handle ICE candidates
        @pc.on("icecandidate")
        async def on_ice_candidate(event):
            await self.handleIce(client_id, event)

        self.connections[client_id] = pc

        remote_offer = RTCSessionDescription(sdp=candidate['sdp'], type=candidate['type'])
        await pc.setRemoteDescription(remote_offer)
        
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await self.sio.emit('answer', json.dumps({
            'host_sid': remote_sid,  
            'sdp': pc.localDescription.sdp, 
            'type': pc.localDescription.type, 
            'room_id': self.room_id
        }), namespace='/connect')

    async def connectToSignallingServer(self):
        # Listen for events from the server within the '/connect' namespace
        self.sio.on('status', self.handle_status, namespace='/connect')
        self.sio.on('answer', self.handle_answer, namespace='/connect')
        self.sio.on('disconnect', self.handle_disconnect, namespace='/connect')
        self.sio.on('candidates', self.chooseCandidate, namespace='/connect')

        # Connect to the server with the '/connect' namespace
        await self.sio.connect(self.server_url, namespaces=['/connect'])

        # Verify the connection to the namespace before emitting 'join_room'
        if self.sio.connected:
            print("Joining room!")
            await self.sio.emit('join_room', {'room_id': self.room_id}, namespace='/connect')
        else:
            print("Failed to connect to the signaling server on '/connect' namespace")


    async def chooseCandidate(self, offer):
        offerDict = json.loads(offer)
        if offerDict:
            remote_sid, candidate = list(offerDict.items())[0]
            await self.sendAnswerAndConnect(remote_sid, candidate)

    async def broadcastOffer(self):
        await self.connectToSignallingServer()
        for client_id in self.connections.keys():
            await self.sendOffer(client_id)

async def main():
    rtc_node = RTCNode()
    await rtc_node.broadcastOffer()
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
