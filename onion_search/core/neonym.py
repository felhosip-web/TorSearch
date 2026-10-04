# Copyright 2026 HES Projects by FePe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Tor network identity, SOCKS/control checks, and NEWNYM circuit signaling.
Developed by HES Projects by FePe.
"""
from pathlib import Path
import random
import socket
import time
import requests


def find_tor_cookie():
    """Search common Tor data directories for the control_auth_cookie file."""
    candidates = [
        Path.home() / ".tor" / "control_auth_cookie",
        Path("/var/run/tor/control.authcookie"),
        Path("/run/tor/control.authcookie"),
    ]
    for base in [
        Path.home() / ".local" / "share",
        Path.home() / ".tor",
        Path.home() / ".config",
    ]:
        try:
            for p in base.rglob("control_auth_cookie"):
                candidates.append(p)
        except Exception:
            pass
    try:
        for p in Path.home().rglob("control_auth_cookie"):
            if "TorBrowser" in str(p):
                candidates.append(p)
                break
    except Exception:
        pass
    for c in candidates:
        if c.exists():
            return c
    return None


def send_newnym_via_control(control_port=9051, password=None):
    """Send SIGNAL NEWNYM to Tor control port using stem or direct socket."""
    ports_to_try = [control_port]
    if control_port == 9051:
        ports_to_try.append(9151)
    else:
        ports_to_try.append(9051)
    cookie_file = find_tor_cookie()
    last_err = "ismeretlen"
    for port in ports_to_try:
        try:
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(port=port) as c:
                try:
                    c.authenticate()
                    c.signal(Signal.NEWNYM)
                    return True, f"stem OK @ {port}"
                except Exception:
                    try:
                        c.authenticate(password="")
                        c.signal(Signal.NEWNYM)
                        return True, f"stem OK @ {port} (empty)"
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            s = socket.socket()
            s.settimeout(4)
            s.connect(("127.0.0.1", port))
            s.sendall(b'AUTHENTICATE ""\r\n')
            resp = s.recv(2048).decode()
            if "515" in resp and cookie_file:
                try:
                    cookie_data = cookie_file.read_bytes().hex()
                    s.sendall(f"AUTHENTICATE {cookie_data}\r\n".encode())
                    resp = s.recv(2048).decode()
                except Exception:
                    pass
            s.sendall(b"SIGNAL NEWNYM\r\n")
            resp2 = s.recv(2048).decode()
            s.close()
            if "250" in resp2:
                return True, f"raw socket OK @ {port}"
        except Exception as e:
            last_err = e
            continue
    return False, f"ControlPort nem elerheto {ports_to_try} - {last_err}"


def get_tor_circuit_status(control_port=9051, password=None):
    """Retrieve Tor circuit status via control port."""
    ports_to_try = [control_port]
    if control_port == 9051:
        ports_to_try.append(9151)
    else:
        ports_to_try.append(9051)
    cookie_file = find_tor_cookie()
    last_err = "ismeretlen"
    for port in ports_to_try:
        try:
            from stem.control import Controller
            with Controller.from_port(port=port) as c:
                try:
                    c.authenticate()
                    info = c.get_info("circuit-status")
                    return True, info
                except Exception:
                    try:
                        c.authenticate(password="")
                        info = c.get_info("circuit-status")
                        return True, info
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            s = socket.socket()
            s.settimeout(4)
            s.connect(("127.0.0.1", port))
            s.sendall(b'AUTHENTICATE ""\r\n')
            resp = s.recv(2048).decode()
            if "515" in resp and cookie_file:
                try:
                    cookie_data = cookie_file.read_bytes().hex()
                    s.sendall(f"AUTHENTICATE {cookie_data}\r\n".encode())
                    resp = s.recv(2048).decode()
                except Exception:
                    pass
            s.sendall(b"GETINFO circuit-status\r\n")
            
            resp2 = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                resp2 += chunk
                if b"250 OK" in resp2:
                    break
            
            s.close()
            resp2_text = resp2.decode()
            if "250-circuit-status=" in resp2_text or "250+circuit-status=" in resp2_text:
                info_parts = resp2_text.split("circuit-status=", 1)
                if len(info_parts) > 1:
                    info = info_parts[1].split("250 OK")[0].strip()
                    return True, info
            elif "250 OK" in resp2_text:
                return True, ""
        except Exception as e:
            last_err = e
            continue
    return False, f"Nem sikerult lekerdezni a circuit-statust: {last_err}"


def check_tor_socks(proxy_port):
    """Verify SOCKS proxy connectivity against check.torproject.org."""
    try:
        proxies = {
            "http": f"socks5h://127.0.0.1:{proxy_port}",
            "https": f"socks5h://127.0.0.1:{proxy_port}",
        }
        r = requests.get("https://check.torproject.org/api/ip", proxies=proxies, timeout=8)
        if r.status_code == 200:
            j = r.json()
            if j.get("IsTor"):
                return True, f"SOCKS OK - IP: {j.get('IP')}"
            else:
                return False, "SOCKS valaszol de nem Tor"
        else:
            return False, f"SOCKS HTTP {r.status_code}"
    except Exception as e:
        return False, f"SOCKS hiba: {e}"


def check_control_port(ctrl_port):
    """Check if Tor control port is accessible and responding."""
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect(("127.0.0.1", ctrl_port))
        s.sendall(b'AUTHENTICATE ""\r\n')
        resp = s.recv(1024).decode()
        s.close()
        if "250" in resp or "515" in resp:
            return True, "ControlPort OK"
        else:
            return False, f"Control valasz: {resp.strip()}"
    except Exception as e:
        return False, f"Control hiba: {e}"


class TorController:
    """Manages Tor control interactions, port auto-detection, and NEWNYM signaling."""

    def __init__(self, on_sessions_reset=None):
        self.on_sessions_reset = on_sessions_reset
        self.last_newnym = 0

    def detect_working_tor(self, preferred_port="9050"):
        """Probe available SOCKS ports (9150, 9050, or preferred) for active Tor."""
        ports_to_check = ["9150", "9050"]
        if preferred_port not in ports_to_check:
            ports_to_check.append(preferred_port)
        for port in ports_to_check:
            ok, msg = check_tor_socks(port)
            if ok:
                return port, True, msg
        for port in ["9150", "9050"]:
            try:
                s = socket.socket()
                s.settimeout(2)
                s.connect(("127.0.0.1", int(port)))
                s.close()
                return (
                    port,
                    False,
                    f"SOCKS port {port} nyitva, de Tor IP check nem ment (pysocks hianyzik?)",
                )
            except Exception:
                pass
        return preferred_port, False, "Egyik SOCKS port sem elerheto (9050,9150)"

    def check_socks(self, port):
        return check_tor_socks(port)

    def check_control(self, port):
        return check_control_port(int(port))

    def trigger_newnym(self, control_port=9051, reason="manual"):
        """Send NEWNYM signal through control port and reset active sessions."""
        now = time.time()
        if reason.startswith("auto") and now - self.last_newnym < 12:
            return False, f"Auto skip - {now - self.last_newnym:.1f}s < 12s"

        if self.on_sessions_reset:
            try:
                self.on_sessions_reset()
            except Exception:
                pass

        ok, msg = send_newnym_via_control(control_port=int(control_port))
        if ok:
            self.last_newnym = now
            time.sleep(4)
            c_ok, c_info = get_tor_circuit_status(control_port=int(control_port))
            if c_ok and c_info:
                msg += f"\n[TOR] Circuit status:\n{c_info}"
            return True, msg
        return False, msg
