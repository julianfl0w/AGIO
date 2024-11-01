import argparse
import asyncio
import logging
import random
import string
import sys
import json

import websockets as ws
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import AudioStreamTrack
from aiortc.contrib.media import MediaPlayer


logger = logging.getLogger('audio_stream')

class WebSocketClient():
    def __init__(self, url='ws://localhost:8188/'):
        self._url = url
        self.connection = None
        self._transactions = {}

    async def connect(self):
        self.connection = await ws.connect(self._url,
                                           subprotocols=['janus-protocol'],
                                           ping_interval=10,
                                           ping_timeout=10,
                                           compression=None)
        if self.connection.open:
            asyncio.ensure_future(self.receive_message())
            logger.info('WebSocket connected')
            return self

    def transaction_id(self):
        return ''.join(random.choice(string.ascii_letters) for x in range(12))

    async def send(self, message):
        tx_id = self.transaction_id()
        message.update({'transaction': tx_id})
        tx = asyncio.get_event_loop().create_future()
        self._transactions[tx_id] = tx
        try:
            await asyncio.gather(self.connection.send(json.dumps(message)), tx)
        except Exception as e:
            tx.set_result(e)
        return tx.result()

    async def receive_message(self):
        try:
            async for message in self.connection:
                data = json.loads(message)
                tx_id = data.get('transaction')
                if tx_id and tx_id in self._transactions:
                    self._transactions[tx_id].set_result(data)
                    del self._transactions[tx_id]
        except Exception:
            logger.error('WebSocket failure')
        logger.info('Connection closed')

    async def close(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
        self._transactions = {}


class JanusPlugin:
    def __init__(self, session, handle_id):
        self._session = session
        self._handle_id = handle_id

    async def send_message(self, message):
        logger.info('Sending message to the plugin')
        message.update({'janus': 'message', 'handle_id': self._handle_id})
        return await self._session.send(message)


class JanusSession:
    def __init__(self, url='ws://localhost:8188/'):
        self._websocket = None
        self._url = url
        self._handles = {}
        self._session_id = None
        self._ka_interval = 15
        self._ka_task = None

    async def send(self, message):
        message.update({'session_id': self._session_id})
        return await self._websocket.send(message)

    async def create(self):
        self._websocket = await WebSocketClient(self._url).connect()
        response = await self.send({'janus': 'create'})
        self._session_id = response['data']['id']
        self._ka_task = asyncio.ensure_future(self._keepalive())
        logger.info(f'Session created with ID: {self._session_id}')

    async def attach(self, plugin):
        response = await self.send({'janus': 'attach', 'plugin': plugin})
        handle_id = response['data']['id']
        handle = JanusPlugin(self, handle_id)
        self._handles[handle_id] = handle
        logger.info('Handle attached')
        return handle
    async def destroy(self):
        logger.info('Destroying session')
        if self._session_id:
            await self.send({'janus': 'destroy'})
            self._session_id = None
        if self._ka_task:
            self._ka_task.cancel()
            try:
                await self._ka_task
            except asyncio.CancelledError:
                pass  # This is expected, so we can safely ignore it
            self._ka_task = None
        self._handles = {}

        logger.info('Closing WebSocket')
        if self._websocket:
            await self._websocket.close()
            self._websocket = None


    async def _keepalive(self):
        while True:
            await self.send({'janus': 'keepalive'})
            await asyncio.sleep(self._ka_interval)


async def run(pc, player, session, room_id):
    # Add audio track from player or file
    if player and player.audio:
        pc.addTrack(player.audio)
    else:
        pc.addTrack(AudioStreamTrack())

    await session.create()
    plugin = await session.attach('janus.plugin.audiobridge')

    # Join the audiobridge room
    join_request = {
        'body': {'request': 'join', 'room': room_id, 'display': 'AudioStreamer', 'audio': True}
    }
    response = await plugin.send_message(join_request)

    # Handle the SDP offer from Janus
    if 'jsep' in response:
        await handle_jsep(plugin, pc, response['jsep'])
    else:
        die

    logger.info('Running for a while...')
    await asyncio.sleep(5)


async def handle_jsep(plugin, pc, jsep):
    offer = RTCSessionDescription(sdp=jsep['sdp'], type=jsep['type'])
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send SDP answer back to Janus
    await plugin.send_message({
        'body': {},
        'jsep': {
            'type': pc.localDescription.type,
            'sdp': pc.localDescription.sdp
        }
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Janus Audio Streamer')
    parser.add_argument('url', help='Janus WebSocket URL, e.g. ws://localhost:8188/')
    parser.add_argument('--play-from', help='Audio file path')
    parser.add_argument('--room-id', type=int, default=1234, help='Audiobridge room ID')
    parser.add_argument('--verbose', '-v', action='count')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    session = JanusSession(args.url)
    pc = RTCPeerConnection()
    player = MediaPlayer(args.play_from) if args.play_from else None

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run(pc=pc, player=player, session=session, room_id=args.room_id))
        logger.info('Streaming completed')
    except Exception as e:
        logger.exception('Streaming failed')
    finally:
        loop.run_until_complete(pc.close())
        loop.run_until_complete(session.destroy())
