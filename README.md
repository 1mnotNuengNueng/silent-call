# silent-call

This project is a LAN voice call desktop application built with Python and PyQt6.

Main files:

- `silent-call/server.py` runs the signaling server
- `silent-call/app.py` runs the GUI client
- `silent-call/client.py` runs a simple command line client
- `silent-call/app_config.json` stores the client configuration

## System Requirements

- Windows
- Python 3.11 or newer
- Working microphone and speaker
- All devices must be on the same LAN and able to reach each other

## Installation

1. Open a terminal in this folder.
2. Go to the project directory.

```powershell
cd "silent-call"
```

3. Create a virtual environment.

```powershell
python -m venv .venv
```

4. Activate the virtual environment.

```powershell
.venv\Scripts\Activate.ps1
```

5. Install dependencies.

```powershell
pip install -r requirements.txt
```

## ENV / Configuration

This project does not currently require a `.env` file. It uses `app_config.json` for runtime configuration instead.

Example `silent-call/app_config.json`:

```json
{
  "server_ip": "10.34.104.20",
  "primary_number": "5555555555",
  "secondary_number": "0000000000",
  "listen_port": 6002
}
```

Configuration fields:

- `server_ip`: IP address of the machine running `server.py`
- `primary_number`: phone number for this client, must be exactly 10 digits
- `secondary_number`: secondary number stored in the UI
- `listen_port`: port used by this client to accept peer connections

Important notes:

- Each client must use a unique `primary_number`
- Each client should use a unique `listen_port`
- If you run the app on multiple machines, update `app_config.json` on each machine with its own values

## How to Run

### 1. Start the signaling server

On the server machine:

```powershell
cd "silent-call"
python server.py
```

If it starts correctly, you should see:

```text
Signaling server running...
```

### 2. Configure the client

Before starting a client, edit `silent-call/app_config.json` and set:

- `server_ip` to the server machine IP
- `primary_number` to the current machine's phone number
- `listen_port` to the current machine's listening port

### 3. Start the GUI client

On each client machine:

```powershell
cd "silent-call"
python app.py
```

If the configuration is valid, the app will try to connect to the server automatically.

## Basic Usage

1. Start `server.py` first.
2. Start `app.py` on at least two machines.
3. Make sure each machine uses a different `primary_number`.
4. On the caller machine, enter the target 10-digit number and start the call.
5. On the receiver machine, accept the incoming call.
6. Both users will enter the chat verification screen before voice communication starts.
7. Each side must send one question, answer the peer's question, and press `Approve Identity`.
8. When both sides approve, the app moves to the in-call screen.
9. End the call by pressing hang up.

## CLI Test Client

If you want to test with the command line client:

```powershell
cd "silent-call"
python client.py
```

Then provide:

- Server IP
- Your own 10-digit number
- Target 10-digit number

Note: `client.py` is a simple test client. The main application flow is intended to be used through `app.py`.

## Common Issues

### `PyAudioWPatch` installation fails

- Make sure you are running on Windows
- Upgrade `pip` first:

```powershell
python -m pip install --upgrade pip
```

- Use a Python version supported by the package

### Calls do not connect

- Make sure `server.py` is still running
- Make sure `server_ip` is correct
- Make sure both clients are on the same LAN
- Make sure the firewall is not blocking port `5000` or each client's `listen_port`

### `number already registered` error

- Another client is already using the same `primary_number`
- Change the number in `app_config.json` or in the app Settings screen
