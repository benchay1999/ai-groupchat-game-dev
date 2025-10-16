import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from game import Game
from ai import AIHandler
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

game = Game()
connections = {}  # WebSocket connections, but since single player, maybe just one
ai_handler = AIHandler(game, connections)
rooms = {}  # room_code -> {'game': Game, 'ai_handler': AIHandler, 'connections': {}}


@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_id: str):
    await websocket.accept()
    if room_code not in rooms:
        game = Game()
        connections = {}
        ai_handler = AIHandler(game, connections)
        rooms[room_code] = {'game': game, 'ai_handler': ai_handler, 'connections': connections}
    else:
        connections = rooms[room_code]['connections']
    connections[player_id] = websocket
    try:
        await rooms[room_code]['ai_handler'].start_game(websocket, room_code, player_id)
        while True:
            data = await websocket.receive_json()
            data['room_code'] = room_code  # Add for handling
            await rooms[room_code]['ai_handler'].handle_message(data, websocket)
    except WebSocketDisconnect:
        del connections[player_id]
        if not connections:
            del rooms[room_code]  # Clean up empty rooms

# Additional routes if needed, e.g., start game
@app.get("/start/{room_code}")
async def start_game(room_code: str):
    if room_code in rooms:
        rooms[room_code]['game'].reset()
        return {"message": "Game started in room"}
    return {"message": "Room not found"}
