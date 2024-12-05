import os
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
from pydub import AudioSegment
from pydub.effects import speedup
import uvicorn
from io import BytesIO


#FASE 1 PROJETO SHADOW BACKEND 
app = FastAPI()

origins = [
    "https://shadow-chat-iota.vercel.app/",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.active_connections[room_id].remove(websocket)
        if not self.active_connections[room_id]:
            del self.active_connections[room_id]

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, room_id: str, message: dict, sender: WebSocket):
        for connection in self.active_connections.get(room_id, []):
            if connection != sender:
                await connection.send_json(message)

manager = ConnectionManager()

def modulate_audio(audio_data: bytes) -> bytes:

    audio = AudioSegment.from_file(BytesIO(audio_data), format="wav")
    
    lowered_pitch_audio = audio._spawn(audio.raw_data, overrides={
        "frame_rate": int(audio.frame_rate * 0.75) 
    }).set_frame_rate(audio.frame_rate)
    
    delay = AudioSegment.silent(duration=50)
    
    robotic_audio = lowered_pitch_audio.overlay(delay + lowered_pitch_audio - 10)
    output = BytesIO()
    robotic_audio.export(output, format="wav")
    return output.getvalue()

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            if message_type == "audio":
                audio_data = base64.b64decode(data["audio"])
                
                modulated_audio = modulate_audio(audio_data)
                
                modulated_audio_base64 = base64.b64encode(modulated_audio).decode("utf-8")
                
                await manager.broadcast(room_id, {"type": "audio", "audio": modulated_audio_base64}, websocket)
            elif message_type == "message":
                await manager.broadcast(room_id, data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, ws_max_size=16 * 1024 * 1024)
