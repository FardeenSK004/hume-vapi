# Huva - Hume EVI Relay

Huva is a lightweight FastAPI-based relay server for [Hume AI's Empathic Voice Interface (EVI)](https://hume.ai/). It allows you to connect a web browser's microphone and speakers to Hume's EVI using a Python backend as a proxy.

## Features

- **Bidirectional Streaming**: Seamlessly pipes audio from the browser to Hume and back.
- **Protocol Translation**: Converts browser-side raw PCM (Linear16) to Hume's expected formats.
- **Secure Context Handling**: Includes checks for secure contexts (HTTPS/Localhost) required for microphone access.
- **Detailed Logging**: Built-in logging in both the terminal and the browser UI to monitor audio flow and EVI events.
- **FastAPI Backend**: Uses an asynchronous architecture for low-latency communication.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- A Hume AI API Key and Config ID

## Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/FardeenSK004/hume-vapi.git
   cd hume-vapi
   ```

2. **Install dependencies**:
   Using `uv`:

   ```bash
   uv sync
   ```

   Using `pip`:

   ```bash
   pip install fastapi uvicorn hume[microphone] python-dotenv jinja2 websockets
   ```

3. **Configure environment variables**:
   Create a `.env` file in the root directory:
   ```env
   HUME_API_KEY=your_api_key_here
   HUME_CONFIG_ID=your_config_id_here
   HUME_SECRET_KEY=your_secret_key_here
   ```

## Usage

1. **Start the server**:

   ```bash
   uv run uvicorn server:app --reload --port 8000
   ```

2. **Open the interface**:
   Navigate to `http://localhost:8000` in your browser.

   > **Note**: Modern browsers require a "Secure Context" for microphone access. `localhost` is treated as secure, but if you are accessing this over a network, you must use HTTPS.

3. **Interact**:
   - Click **Start Conversation**.
   - Grant microphone permissions when prompted.
   - Start talking! The logs will show transcribing results and audio playback status.

## Project Structure

- `server.py`: FastAPI server that handles WebSocket connections and communicates with Hume's SDK.
- `templates/index.html`: The frontend UI and audio processing logic.
- `pyproject.toml`: Project dependencies.
