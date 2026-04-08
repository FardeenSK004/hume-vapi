import os
import asyncio
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from hume.client import AsyncHumeClient
from hume.empathic_voice.types import (
    AudioInput,
    AudioConfiguration,
    SessionSettings,
)

# Load environment variables
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

HUME_API_KEY = os.getenv("HUME_API_KEY")
HUME_CONFIG_ID = os.getenv("HUME_CONFIG_ID")


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


def get_voice_map():
    voice_configs = os.getenv("VOICE_CONFIGS", "")
    voice_map = {}
    if voice_configs:
        # Expected format: "Name1:ID1,Name2:ID2"
        pairs = voice_configs.split(",")
        for pair in pairs:
            if ":" in pair:
                name, config_id = pair.split(":", 1)
                voice_map[name.strip().lower()] = config_id.strip()
    return voice_map


@app.get("/voices")
async def get_voices():
    voice_map = get_voice_map()
    return [{"name": name.capitalize(), "key": name} for name in voice_map.keys()]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, voice: str = None):
    await websocket.accept()
    print("[WS] Browser connected")

    # Resolve config_id from voice name or fall back to default
    voice_map = get_voice_map()
    active_config = HUME_CONFIG_ID
    
    if voice:
        voice_key = voice.strip().lower()
        if voice_key in voice_map:
            active_config = voice_map[voice_key]
            print(f"[WS] Resolved voice '{voice}' to config_id: {active_config}")
        else:
            print(f"[WS] Warning: Voice '{voice}' not found in map. Using default.")

    client = AsyncHumeClient(api_key=HUME_API_KEY)

    try:
        async with client.empathic_voice.chat.connect(
            config_id=active_config
        ) as hume_socket:
            # Disable keepalive pings to avoid the websockets legacy protocol bug
            # that causes AssertionError when pings conflict with writes.
            if hasattr(hume_socket, "_websocket"):
                hume_socket._websocket.ping_interval = None

            print(f"[HUME] Connected to Hume AI (config: {active_config})")

            # Send session settings with audio configuration
            audio_config = AudioConfiguration(
                sample_rate=48000,
                channels=1,
                encoding="linear16",
            )
            session_settings = SessionSettings(audio=audio_config)
            await hume_socket.send_publish(message=session_settings)
            print("[HUME] Sent session settings (48kHz, mono, linear16)")

            send_count = 0
            recv_count = 0

            async def from_hume():
                """Receive messages from Hume and forward to browser."""
                nonlocal recv_count
                try:
                    async for message in hume_socket:
                        msg_type = getattr(message, "type", None)
                        recv_count += 1

                        if msg_type == "audio_output":
                            if recv_count <= 5 or recv_count % 20 == 0:
                                print(f"[HUME→BROWSER] audio_output #{recv_count} (data len: {len(getattr(message, 'data', ''))})")
                            await websocket.send_json(message.model_dump())

                        elif msg_type in ["user_message", "assistant_message"]:
                            msg_content = ""
                            msg_obj = getattr(message, "message", None)
                            if msg_obj:
                                msg_content = getattr(msg_obj, "content", "")
                            print(f"[HUME→BROWSER] {msg_type}: {msg_content[:80]}")
                            await websocket.send_json(message.model_dump())

                        elif msg_type == "chat_metadata":
                            print(f"[HUME→BROWSER] chat_metadata")
                            await websocket.send_json(message.model_dump())

                        elif msg_type == "error":
                            err_msg = getattr(message, "message", str(message))
                            print(f"[HUME] ERROR: {err_msg}")
                            await websocket.send_json(
                                {"type": "error", "message": err_msg}
                            )
                        else:
                            print(f"[HUME] Event: {msg_type}")

                except Exception as e:
                    print(f"[HUME] from_hume error: {e}")
                    import traceback
                    traceback.print_exc()

            async def to_hume():
                """Receive audio from browser and forward to Hume."""
                nonlocal send_count
                try:
                    async for raw_bytes in websocket.iter_bytes():
                        if not raw_bytes:
                            continue

                        send_count += 1

                        # Base64 encode the raw PCM bytes and send as AudioInput
                        b64_audio = base64.b64encode(raw_bytes).decode("utf-8")
                        audio_input = AudioInput(data=b64_audio)
                        await hume_socket.send_publish(audio_input)

                        if send_count <= 3 or send_count % 100 == 0:
                            print(f"[BROWSER→HUME] audio chunk #{send_count} ({len(raw_bytes)} bytes)")

                except WebSocketDisconnect:
                    print("[WS] Browser disconnected ")
                except Exception as e:
                    print(f"[WS] to_hume error: {e}")
                    import traceback
                    traceback.print_exc()

            # Run both tasks concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(from_hume()),
                    asyncio.create_task(to_hume()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            print(f"[WS] Session ended. Sent {send_count} audio chunks, received {recv_count} events.")
            print("Session ended successfully")      

    except Exception as e:
        print(f"[HUME] Connection failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

