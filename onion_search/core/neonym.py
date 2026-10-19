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


import logging

logger = logging.getLogger("onion_search")


def check_control_port(ctrl_port):
    """Check if Tor control port is accessible and responding."""
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect(("127.0.0.1", int(ctrl_port)))
        s.sendall(b'AUTHENTICATE ""\r\n')
        resp = s.recv(1024).decode()
        s.close()
        if "250" in resp or "515" in resp:
            return True, "ControlPort OK"
        else:
            return False, f"Control valasz: {resp.strip()}"
    except Exception as e:
        return False, f"Control hiba: {e}"


def probe_tor_socks_port(port, tcp_timeout=2.0, socks_timeout=4.0):
    """
    Perform step-by-step diagnostic on a SOCKS port:
    1. TCP socket reachability test (127.0.0.1:port) with configurable tcp_timeout.
    2. Real Tor connection test via check.torproject.org/api/ip with configurable socks_timeout.
    3. Response latency measurement and IsTor verification.
    """
    port_str = str(port)

    # Step 1: TCP Port reachability check
    try:
        s = socket.socket()
        s.settimeout(tcp_timeout)
        s.connect(("127.0.0.1", int(port)))
        s.close()
    except Exception as e:
        err_msg = getattr(e, "strerror", None) or str(e)
        if "refused" in str(e).lower() or getattr(e, "errno", None) == 111:
            err_fmt = "nem elérhető (Connection refused)"
        elif "timed out" in str(e).lower():
            err_fmt = "nem elérhető (Connection timed out)"
        else:
            err_fmt = f"nem elérhető ({err_msg})"

        return {
            "port": port_str,
            "tcp_open": False,
            "socks_ok": False,
            "is_tor": False,
            "latency_ms": None,
            "ip": None,
            "error": err_fmt,
            "status_str": err_fmt,
        }

    # Step 2: SOCKS5 & Real Tor request test
    proxies = {
        "http": f"socks5h://127.0.0.1:{port_str}",
        "https": f"socks5h://127.0.0.1:{port_str}",
    }
    http_start = time.perf_counter()
    try:
        r = requests.get(
            "https://check.torproject.org/api/ip",
            proxies=proxies,
            timeout=socks_timeout,
        )
        latency_ms = (time.perf_counter() - http_start) * 1000.0

        if r.status_code == 200:
            j = r.json()
            is_tor = bool(j.get("IsTor"))
            ip = j.get("IP", "")
            if is_tor:
                return {
                    "port": port_str,
                    "tcp_open": True,
                    "socks_ok": True,
                    "is_tor": True,
                    "latency_ms": latency_ms,
                    "ip": ip,
                    "error": None,
                    "status_str": f"működik ({latency_ms:.0f} ms, IP: {ip})",
                }
            else:
                return {
                    "port": port_str,
                    "tcp_open": True,
                    "socks_ok": False,
                    "is_tor": False,
                    "latency_ms": latency_ms,
                    "ip": ip,
                    "error": "SOCKS proxy válaszol, de nem Tor hálózat (IsTor: false)",
                    "status_str": "nem Tor (IsTor: false)",
                }
        else:
            return {
                "port": port_str,
                "tcp_open": True,
                "socks_ok": False,
                "is_tor": False,
                "latency_ms": latency_ms,
                "ip": None,
                "error": f"HTTP {r.status_code} hiba",
                "status_str": f"HTTP {r.status_code}",
            }
    except Exception as e:
        latency_ms = (time.perf_counter() - http_start) * 1000.0
        err_str = str(e)
        if "refused" in err_str.lower():
            err_fmt = "nem elérhető (Connection refused)"
        else:
            err_fmt = f"hiba ({err_str[:60]})"
        return {
            "port": port_str,
            "tcp_open": True,
            "socks_ok": False,
            "is_tor": False,
            "latency_ms": latency_ms,
            "ip": None,
            "error": err_fmt,
            "status_str": err_fmt,
        }


def run_tor_diagnostics(
    preferred_port="9050",
    tcp_timeout=2.0,
    socks_timeout=4.0,
    force_full_scan=False,
):
    """
    Run multi-step Tor connectivity diagnostics:
    1. First probe preferred_port (last working or user configured port).
    2. If preferred_port works and force_full_scan is False -> fast-path return.
    3. If preferred_port fails or force_full_scan is True -> full probe of all candidate ports (9050, 9150).
    4. Auto-select working port (preferring 9050 if both work).
    """
    pref_str = str(preferred_port or "9050")
    candidate_ports = ["9050", "9150"]
    if pref_str not in candidate_ports:
        candidate_ports.insert(0, pref_str)

    res_ports = {}

    # Fast-path check of preferred_port
    pref_res = probe_tor_socks_port(
        pref_str, tcp_timeout=tcp_timeout, socks_timeout=socks_timeout
    )
    res_ports[pref_str] = pref_res

    if pref_res["socks_ok"] and pref_res["is_tor"] and not force_full_scan:
        # Fast-path success!
        selected_socks_port = pref_str
        ctrl_map = {"9050": 9051, "9150": 9151}
        pref_ctrl = ctrl_map.get(pref_str, 9051)
        ctrl_ok, ctrl_msg = check_control_port(pref_ctrl)
        selected_ctrl_port = str(pref_ctrl)

        for p in candidate_ports:
            if p != pref_str and p not in res_ports:
                res_ports[p] = {
                    "port": p,
                    "tcp_open": None,
                    "socks_ok": None,
                    "is_tor": None,
                    "latency_ms": None,
                    "ip": None,
                    "error": None,
                    "status_str": "kihagyva (a preferált port működik)",
                }

        active_res = pref_res
        short_msg = (
            f"[✓] Tor kapcsolat aktív — Használt port: 127.0.0.1:{selected_socks_port} "
            f"(Válaszidő: {active_res['latency_ms']:.0f} ms)"
        )
        formatted_report = (
            f"[✓] Tor kapcsolat sikeresen felépült (Preferált port: 127.0.0.1:{selected_socks_port})!\n\n"
            f"Diagnosztika eredménye:\n"
            f"  • 127.0.0.1:{selected_socks_port} → {active_res['status_str']}\n"
            f"  • ControlPort {selected_ctrl_port} → {ctrl_msg}\n\n"
            f"Automatikus beállítás:\n"
            f"  • Aktív proxy: 127.0.0.1:{selected_socks_port}\n"
            f"  • Válaszidő: {active_res['latency_ms']:.0f} ms\n"
            f"  • Tor IP: {active_res['ip'] or 'Ismeretlen'}\n"
        )
        return {
            "success": True,
            "selected_socks_port": selected_socks_port,
            "selected_ctrl_port": selected_ctrl_port,
            "short_msg": short_msg,
            "formatted_report": formatted_report,
            "ports": res_ports,
            "control_ports": {
                selected_ctrl_port: {"ok": ctrl_ok, "msg": ctrl_msg}
            },
            "active_res": active_res,
        }

    # Full scan: probe remaining ports
    for p in ["9050", "9150"]:
        if p not in res_ports:
            res_ports[p] = probe_tor_socks_port(
                p, tcp_timeout=tcp_timeout, socks_timeout=socks_timeout
            )

    ctrl_ok_9051, ctrl_msg_9051 = check_control_port(9051)
    ctrl_ok_9151, ctrl_msg_9151 = check_control_port(9151)

    ok_9050 = res_ports.get("9050", {}).get("socks_ok") and res_ports.get("9050", {}).get("is_tor")
    ok_9150 = res_ports.get("9150", {}).get("socks_ok") and res_ports.get("9150", {}).get("is_tor")

    selected_socks_port = None
    selected_ctrl_port = "9051"
    active_res = None

    if ok_9050:
        selected_socks_port = "9050"
        selected_ctrl_port = "9051" if ctrl_ok_9051 or not ctrl_ok_9151 else "9151"
        active_res = res_ports["9050"]
    elif ok_9150:
        selected_socks_port = "9150"
        selected_ctrl_port = "9151" if ctrl_ok_9151 or not ctrl_ok_9051 else "9051"
        active_res = res_ports["9150"]

    success = selected_socks_port is not None

    status_9050 = res_ports.get("9050", {}).get("status_str", "ismeretlen")
    status_9150 = res_ports.get("9150", {}).get("status_str", "ismeretlen")

    if success and active_res:
        short_msg = (
            f"[✓] Tor kapcsolat aktív — Használt port: 127.0.0.1:{selected_socks_port} "
            f"(Válaszidő: {active_res['latency_ms']:.0f} ms)"
        )
        formatted_report = (
            f"[✓] Tor kapcsolat sikeresen felépült!\n\n"
            f"Diagnosztika eredménye:\n"
            f"  • 127.0.0.1:9050 (rendszer Tor) → {status_9050}\n"
            f"  • 127.0.0.1:9150 (Tor Browser)  → {status_9150}\n"
            f"  • ControlPort 9051 → {ctrl_msg_9051}\n"
            f"  • ControlPort 9151 → {ctrl_msg_9151}\n\n"
            f"Automatikus beállítás:\n"
            f"  • Aktív proxy: 127.0.0.1:{selected_socks_port}\n"
            f"  • Válaszidő: {active_res['latency_ms']:.0f} ms\n"
            f"  • Tor IP: {active_res['ip'] or 'Ismeretlen'}\n"
        )
    else:
        short_msg = "[!] Tor kapcsolat sikertelen — egyetlen SOCKS port sem elérhető"
        formatted_report = (
            f"[!] Tor kapcsolat sikertelen\n\n"
            f"Diagnosztika eredménye:\n"
            f"  • 127.0.0.1:9050  → {status_9050}\n"
            f"  • 127.0.0.1:9150  → {status_9150}\n"
            f"  • ControlPort 9051 → {ctrl_msg_9051}\n"
            f"  • ControlPort 9151 → {ctrl_msg_9151}\n\n"
            f"Lehetséges okok és megoldások:\n"
            f"  1. A rendszer Tor szolgáltatás nincs elindítva\n"
            f"     → sudo systemctl start tor\n"
            f"  2. A Tor Böngésző nincs elindítva\n"
            f"     → Indítsd el a Tor Browser-t\n"
            f"  3. Tűzfal vagy más program blokkolja a portokat\n"
            f"  4. Manuális beállítás: add meg a helyes SOCKS hostot és portot a Beállításokban\n"
        )

    logger.debug(f"[TOR DIAGNOSTICS] Success={success}\n{formatted_report}")

    return {
        "success": success,
        "selected_socks_port": selected_socks_port,
        "selected_ctrl_port": selected_ctrl_port,
        "short_msg": short_msg,
        "formatted_report": formatted_report,
        "ports": res_ports,
        "control_ports": {
            "9051": {"ok": ctrl_ok_9051, "msg": ctrl_msg_9051},
            "9151": {"ok": ctrl_ok_9151, "msg": ctrl_msg_9151},
        },
        "active_res": active_res,
    }


class TorController:
    """Manages Tor control interactions, port auto-detection, and NEWNYM signaling."""

    def __init__(self, on_sessions_reset=None):
        self.on_sessions_reset = on_sessions_reset
        self.last_newnym = 0

    def run_diagnostics(
        self,
        preferred_port="9050",
        tcp_timeout=2.0,
        socks_timeout=4.0,
        force_full_scan=False,
    ):
        """Run complete Tor diagnostic test and auto-select active proxy."""
        return run_tor_diagnostics(
            preferred_port=preferred_port,
            tcp_timeout=tcp_timeout,
            socks_timeout=socks_timeout,
            force_full_scan=force_full_scan,
        )

    def detect_working_tor(self, preferred_port="9050"):
        """Probe available SOCKS ports (9150, 9050, or preferred) for active Tor."""
        diag = self.run_diagnostics(preferred_port=preferred_port)
        if diag["success"]:
            port = diag["selected_socks_port"]
            act = diag["active_res"]
            msg = f"SOCKS OK - IP: {act['ip'] if act else ''} ({act['latency_ms']:.0f} ms)" if act else "SOCKS OK"
            return port, True, msg

        # Fallback check
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
