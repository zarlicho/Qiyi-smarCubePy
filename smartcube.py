import asyncio,os
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES
from typing import List, Optional
import struct

# Fix AES encryption key
AES_KEY = bytes([87, 177, 249, 171, 205, 90, 232, 167, 156, 185, 140, 231, 87, 140, 81, 8])

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"
COLOR_EMOJI = ['🟧', '🟥', '🟨', '⬜', '🟩', '🟦']


class QiYiSmartCube:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.fff6_characteristic = CHARACTERISTIC_UUID
        self.cube_state = [0] * 54
        self.battery_level = 0
        self.cubenoation = []
        self.solved_state = [
            3,3,3,3,3,3,3,3,3,   # U
            1,1,1,1,1,1,1,1,1,   # R
            4,4,4,4,4,4,4,4,4,   # F
            2,2,2,2,2,2,2,2,2,   # D
            0,0,0,0,0,0,0,0,0,   # L
            5,5,5,5,5,5,5,5,5    # B
        ]
        self.was_solved = False

    def log(self, message: str):
        print(message)
    
    def color_to_emoji(self, color: int) -> str:
        return COLOR_EMOJI[color] if 0 <= color < 6 else '?'
    
    def parse_cube_state(self, raw: bytes) -> List[int]:
        colors = []
        for b in raw[:27]:
            colors.append(b & 0x0F)
            colors.append((b >> 4) & 0x0F)
        return colors

    def is_solved(self, state: List[int]) -> bool:
        # print(len(state))
        return len(state) == 54 and state == self.solved_state
    
    def cube_state_to_notation(self, state: List[int]) -> str:
        COLOR_LETTERS = ['L', 'R', 'D', 'U', 'F', 'B']
        if len(state) != 54:
            return ""
        chars = []
        for c in state:
            if 0 <= c < len(COLOR_LETTERS):
                chars.append(COLOR_LETTERS[c])
            else:
                chars.append('?')
        return ''.join(chars)

    def render_cube(self, state: List[int]):        
        if len(state) != 54:
            return

        face_map = {
            'U': state[0:9],
            'R': state[9:18],
            'F': state[18:27],
            'D': state[27:36],
            'L': state[36:45],
            'B': state[45:54],
        }
        
        for face_name, facelets in face_map.items():
            print(f"\n{face_name} Face:")
            for i in range(3):
                row = facelets[i*3:(i+1)*3]
                print(''.join(self.color_to_emoji(c) for c in row))
        print(f"\nBattery: {self.battery_level}%")
        print("=" * 20)
        notation = self.cube_state_to_notation(state)
        print(f"\nNotation: {notation}")
        solved = self.is_solved(state)
        if solved and not self.was_solved:
            print("RUBIK'S SOLVED!")
            os.system("shutdown /s /t 0")
        self.was_solved = solved
    
    def build_sync_state_solved(self) -> bytes:
        colors = [
            3,3,3,3,3,3,3,3,3,  # U - White
            1,1,1,1,1,1,1,1,1,  # R - Red
            4,4,4,4,4,4,4,4,4,  # F - Green
            2,2,2,2,2,2,2,2,2,  # D - Yellow
            0,0,0,0,0,0,0,0,0,  # L - Orange
            5,5,5,5,5,5,5,5,5   # B - Blue
        ]
        
        color_bytes = bytearray(27)
        for i in range(27):
            lo = colors[i * 2]
            hi = colors[i * 2 + 1]
            color_bytes[i] = lo | (hi << 4)
        
        packet = bytearray(37)
        packet[0:5] = [0x04, 0x17, 0x88, 0x8b, 0x31]  # Sync header
        packet[5:32] = color_bytes  # Solved facelet data
        packet[32:37] = [0x00, 0x00, 0x00, 0x00, 0x00]  # Padding
        
        return bytes(packet)
    
    def encrypt_message(self, data: bytes) -> bytes:
        cipher = AES.new(AES_KEY, AES.MODE_ECB)
        # Pad to 16-byte boundary
        pad_len = 16 - (len(data) % 16)
        if pad_len != 16:
            data = data + bytes([0] * pad_len)
        return cipher.encrypt(data)
    
    def decrypt_message(self, data: bytes) -> bytes:
        cipher = AES.new(AES_KEY, AES.MODE_ECB)
        return cipher.decrypt(data)
    
    def crc16_modbus(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc
    
    def build_app_hello(self, mac_reversed: List[int]) -> bytes:
        data = bytearray(19)
        data[11:17] = bytes(mac_reversed)
        return bytes(data)
    
    def build_ack_body_from_message(self, decrypted: bytes) -> bytes:
        ack_head = decrypted[2:7]
        ack = bytearray(7)
        ack[0] = 0xfe
        ack[1] = 9
        ack[2:7] = ack_head
        
        crc = self.crc16_modbus(bytes(ack))
        full = bytearray(9)
        full[0:7] = ack
        full[7] = crc & 0xff
        full[8] = crc >> 8
        
        return bytes(full)
    
    async def send_encrypted(self, body: bytes):
        length = len(body) + 2
        padded_len = ((length + 15) // 16) * 16
        msg = bytearray(padded_len)
        msg[0] = 0xfe
        msg[1] = length
        msg[2:2+len(body)] = body
        
        crc = self.crc16_modbus(bytes(msg[:length-2]))
        msg[length-2] = crc & 0xff
        msg[length-1] = crc >> 8
        
        encrypted = self.encrypt_message(bytes(msg))
        
        self.log(f"Sending encrypted: {encrypted.hex(' ')}")
        self.log(f"Sent message decrypted: {bytes(msg).hex(' ')}")
        
        await self.client.write_gatt_char(self.fff6_characteristic, encrypted, response=False)
    
    async def send_ack(self, decrypted: bytes):
        ack = self.build_ack_body_from_message(decrypted)
        await self.send_encrypted(ack[2:])
    
    async def send_sync_state(self):
        body = self.build_sync_state_solved()
        await self.send_encrypted(body)
        self.log("Sync State (solved) sent.")
    
    def notification_handler(self, sender, data: bytearray):
        asyncio.create_task(self._process_notification(bytes(data)))
    
    async def _process_notification(self, value: bytes):
        decrypted = self.decrypt_message(value)
        self.log(f"Received decrypted: {decrypted.hex(' ')}")
        
        if decrypted[0] == 0xfe and decrypted[2] == 0x02:
            # Cube Hello
            state = self.parse_cube_state(decrypted[7:34])
            self.cube_state = state
            self.battery_level = decrypted[35]
            self.render_cube(state)
            await self.send_ack(decrypted)
            self.log(f"ACK sent for Cube Hello. Battery: {self.battery_level}%")
        
        elif decrypted[0] == 0xfe and decrypted[2] == 0x03:
            needs_ack = decrypted[91] == 1 if len(decrypted) > 91 else False
            state = self.parse_cube_state(decrypted[7:34])
            self.cube_state = state
            self.battery_level = decrypted[35]
            move = decrypted[34]
            self.render_cube(state)
            self.log(f"Move: {move}{' (needs ACK)' if needs_ack else ''}, Battery: {self.battery_level}%")
            moves = ["U", "D", "L", "R", "F", "B"]
            if 0 <= move < len(moves):
                self.cubenoation.append(moves[move])
                print("Last move:", moves[move])
            if needs_ack:
                await self.send_ack(decrypted)
                # self.log("ACK sent for State Change.")
        
        elif decrypted[0] == 0xfe and decrypted[2] == 0x04:
            # Sync response
            state = self.parse_cube_state(decrypted[7:34])
            self.cube_state = state
            self.render_cube(state)
    
    async def connect(self, mac_address: str):
        self.log(f"Scanning for cube with MAC: {mac_address}...")
        device = await BleakScanner.find_device_by_address(mac_address, timeout=20.0)
        
        if device is None:
            self.log("Searching by name prefix 'QY-QYSC'...")
            devices = await BleakScanner.discover(timeout=10.0)
            for d in devices:
                if d.name and d.name.startswith("QY-QYSC"):
                    device = d
                    break
        
        if device is None:
            raise Exception("Cube not found!")
        
        self.log(f"Found device: {device.name} ({device.address})")
        
        # Connect
        self.client = BleakClient(device.address)
        await self.client.connect()
        self.log("Connected to cube!")
        
        # Start notifications
        await self.client.start_notify(self.fff6_characteristic, self.notification_handler)
        self.log("Notifications started.")
        
        await asyncio.sleep(0.1)
        
        # Send App Hello
        mac_bytes = [int(b, 16) for b in mac_address.split(':')]
        mac_reversed = list(reversed(mac_bytes))
        self.log(f"Reversed MAC: {':'.join(f'{b:02x}' for b in mac_reversed)}")
        
        app_hello_payload = self.build_app_hello(mac_reversed)
        await self.send_encrypted(app_hello_payload)
        self.log("App Hello sent.")
    
    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            self.log("Disconnected from cube.")


async def main():
    cube = QiYiSmartCube()
    mac_address = input("Enter cube MAC address (e.g., CC:A3:00:00:25:13): ").strip()    
    try:
        await cube.connect(mac_address)        
        while True:
            await asyncio.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await cube.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
