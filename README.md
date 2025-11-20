# QiYi Smart Cube BLE Client (smartcube.py)

A minimal asynchronous Python client for the QiYi Smart Cube that:
- Discovers and connects to the cube over BLE using `bleak`
- Decrypts/encrypts messages with a fixed AES-ECB key
- Parses cube state, last move, and battery level
- Renders the cube faces in the terminal using color emoji
- Sends ACKs (CRC16/MODBUS) and optional sync messages
- Detects solved state

---

## Features

- BLE discovery & connection via `bleak`
- AES-ECB decrypt/encrypt using a fixed key (hardcoded in the script)
- Message framing with CRC16/MODBUS checksum
- Notification handling with:
  - 0x02: Cube Hello (initial state + battery)
  - 0x03: State Change (last move + updated state + battery)
  - 0x04: Sync Response
- Cube state parsing into 54 facelets and pretty terminal output
- Simple move logging (U, D, L, R, F, B)
- Optional “send solved state” sync payload
- Asynchronous architecture using `asyncio`

---

## Requirements

- Python: 3.9+ (3.10+ recommended)
- BLE adapter (Bluetooth 4.0+)
- OS support:
  - Windows 10/11
  - Linux (BlueZ required)
  - macOS (10.11+)

Python dependencies:
- bleak==1.1.1
- pycryptodome==3.20.0

Note: The provided `requirements.txt` currently contains a typo for pycryptodome. Install the correct package name manually or fix the file.

---

## Installation

It’s best to use a virtual environment.

Windows (PowerShell or cmd):
```
python -m venv .venv
.venv\Scripts\activate
pip install bleak==1.1.1 pycryptodome==3.20.0
```

Linux/macOS:
```
python3 -m venv .venv
source .venv/bin/activate
pip install bleak==1.1.1 pycryptodome==3.20.0
```
---

## Getting the Cube MAC Address

- Turn on the QiYi Smart Cube (wake the sensor by moving it).
- Find the device in your OS Bluetooth settings and copy the MAC address, e.g., `CC:A3:00:00:25:13`.
- The code will also try to discover devices by name prefix `QY-QYSC` if a direct address lookup fails. However, the App Hello step uses the input MAC address, so providing the correct MAC is strongly recommended.

---

## Usage

Run the script directly:
```
python smartcube.py
```

You will be prompted:
```
Enter cube MAC address (e.g., CC:A3:00:00:25:13):
```

On successful connection, you’ll see:
- Faces U, R, F, D, L, B printed as 3×3 with emojis
- Battery percentage
- A “Notation” line (see below)
- “Last move: ...” when turns are detected

To stop:
- Press Ctrl+C to gracefully disconnect.

---

## Output and Data Model

Color/emoji mapping used in output:
- 0: Orange 🟧
- 1: Red 🟥
- 2: Yellow 🟨
- 3: White ⬜
- 4: Green 🟩
- 5: Blue 🟦

Solved state mapping as used internally (indices 0..53):
- U = 3 (White)
- R = 1 (Red)
- F = 4 (Green)
- D = 2 (Yellow)
- L = 0 (Orange)
- B = 5 (Blue)

“Notation” line:
- This is not a move sequence. It is a 54-character facelet color string derived from color indices using the mapping:
  - 0 → L
  - 1 → R
  - 2 → D
  - 3 → U
  - 4 → F
  - 5 → B
- It’s a face-color encoding tied to the cube’s color indices, not standard Singmaster turn notation.

Last move logging:
- The script maps a single move byte to one of: `["U", "D", "L", "R", "F", "B"]`.
- No prime (`'`) or double (`2`) turns are encoded; only face identifiers.

Battery:
- Parsed from the message and printed in percent.

---
---

## API Overview (smartcube.py)

Class: `QiYiSmartCube`

- Attributes:
  - `client`: `BleakClient | None`
  - `cube_state`: list of 54 color indices
  - `battery_level`: int
  - `was_solved`: bool

- Main methods:
  - `async connect(mac_address: str)`: Scan and connect; sets up notifications; sends App Hello (requires correct MAC bytes in reverse order).
  - `async disconnect()`: Gracefully disconnects the BLE client.
  - `render_cube(state: List[int])`: Prints faces with emojis, battery, derived “Notation”, and triggers solved logic.
  - `is_solved(state: List[int]) -> bool`: Checks against the predefined solved layout.
  - `cube_state_to_notation(state: List[int]) -> str`: Converts 54 color indices to a 54-char color-letter string (not a turn sequence).
  - `parse_cube_state(raw: bytes) -> List[int]`: Unpacks 27 bytes of packed nibbles into 54 color indices.
  - `async send_sync_state()`: Sends a “solved-state” sync payload to the cube (for testing).
  - Internal helpers for AES encrypt/decrypt, CRC16/MODBUS, and ACK building.

Entry point:
- The bottom of the file defines an `async def main()` that prompts for MAC and runs the connection loop:
```
if __name__ == "__main__":
    asyncio.run(main())
```

---
---

## Troubleshooting

- Module not found: Crypto
  - Ensure you installed `pycryptodome` (correct spelling). Import path is `from Crypto.Cipher import AES`.
- BLE not working (Windows)
  - Make sure Bluetooth is enabled; update Bluetooth drivers; run terminal as normal user (admin usually not needed).
- BLE not working (Linux)
  - Ensure BlueZ is installed; your user is in the appropriate bluetooth groups; service is running.
- “Cube not found!”
  - Ensure the cube is awake and near the computer.
  - Confirm the MAC address is correct.
  - Try the discovery fallback: the code searches for devices named with prefix `QY-QYSC`.
- Decryption looks wrong
  - This script uses a fixed AES-ECB key. If QiYi firmware/protocol changes, messages may not decrypt properly.
- Immediate shutdown when solved
  - See the Safety section and disable the shutdown line before testing.

---

## Notes and Disclaimers

- Protocol details are inferred; not an official QiYi SDK. Use at your own risk.
- The AES key is hardcoded for interoperability; ensure you’re complying with local laws and device terms.
- This code is for educational and research purposes.

---

## Acknowledgements

- [bleak](https://github.com/hbldh/bleak)
- [PyCryptodome](https://github.com/Legrandin/pycryptodome)