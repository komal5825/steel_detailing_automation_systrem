from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/{uuid}")
async def websocket_endpoint(websocket: WebSocket, uuid: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received for {uuid}: {data}")
    except WebSocketDisconnect:
        print(f"Client {uuid} disconnected")
