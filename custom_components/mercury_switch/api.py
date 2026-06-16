"""API client for Mercury SE109P Pro PoE Switch."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta


from .const import POE_PORT_COUNT, ETH_PORT_COUNT

_LOGGER = logging.getLogger(__name__)

_MERCURY_KEY = "RDpbLfCPsJZ7fiv"
_MERCURY_BIG_KEY = (
    "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD02KZ"
    "ciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV57fQMc"
    "8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZLEal1h0t9YQW0Ko7oBwmCAH"
    "oic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"
)


def _mercury_encode(password: str) -> str:
    """Compute Mercury's custom 'hex_md5' (XOR-based encoding)."""
    result: list[str] = []
    max_len = max(len(password), len(_MERCURY_KEY))
    for i in range(max_len):
        l_val = 187
        i_val = 187
        if i >= len(password):
            i_val = ord(_MERCURY_KEY[i])
        else:
            if i >= len(_MERCURY_KEY):
                l_val = ord(password[i])
            else:
                l_val = ord(password[i])
                i_val = ord(_MERCURY_KEY[i])
        result.append(_MERCURY_BIG_KEY[(l_val ^ i_val) % len(_MERCURY_BIG_KEY)])
    return "".join(result)


def _do_login_sync(host: str, username: str, password: str) -> tuple[str | None, int | None]:
    """Synchronous login using urllib (no aiohttp dependency).

    Returns (cookie_str, g_tid) on success, (None, None) on failure.
    """
    import urllib.request
    import urllib.parse
    import urllib.error

    encoded_pw = _mercury_encode(password)
    data = urllib.parse.urlencode({
        "username": username,
        "plain_password": password,
        "password": encoded_pw,
        "isIe": "false",
        "logon": "登录",
    }).encode()

    try:
        req = urllib.request.Request(f"http://{host}/logon.cgi", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            set_cookie = resp.headers.get("Set-Cookie", "")
            status = resp.status
            _LOGGER.debug("Login POST status=%d, Set-Cookie=%s", status, set_cookie[:80] if set_cookie else "NONE")
            cookie_match = re.search(r"SessionID=([^;]+)", set_cookie)
            if not cookie_match:
                _LOGGER.warning("No SessionID in login response. Headers: %s", dict(resp.headers))
                return None, None, "登录响应中没有SessionID cookie"
            cookie_str = f"SessionID={cookie_match.group(1)}"

        # Verify
        _LOGGER.debug("Verifying login with GET /")
        req2 = urllib.request.Request(
            f"http://{host}/",
            headers={"Cookie": cookie_str},
        )
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            html = resp2.read().decode()
            tid_match = re.search(r"(?:\bvar\s+)?\bg_tid\s*=\s*(\d+);", html)
            if tid_match:
                _LOGGER.debug("Login verified, g_tid=%s", tid_match.group(1))
                return cookie_str, int(tid_match.group(1)), None

            has_logon = "logonInfo" in html
            has_username = "用户名" in html
            err_code = -1
            err_match = re.search(r"logonInfo\s*=\s*new\s+Array\s*\((\d+)", html)
            if err_match:
                err_code = int(err_match.group(1))
            _LOGGER.warning(
                "Login verify failed. has_logonInfo=%s, has_username=%s, errType=%d, html_preview=%s",
                has_logon, has_username, err_code, html[:200],
            )
            if has_logon:
                return None, None, f"登录验证失败(errType={err_code})"
            _LOGGER.warning(
                "Login verify returned unexpected HTML:\n%s",
                html[:500],
            )
            return None, None, f"登录验证返回了意外的页面内容(前200字符:{html[:200]})"

    except urllib.error.HTTPError as exc:
        _LOGGER.error("Login HTTP error: code=%d, msg=%s", exc.code, exc.reason)
        return None, None, f"HTTP错误 {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        _LOGGER.error("Login URL error: %s", exc.reason)
        return None, None, f"连接失败: {exc.reason}"
    except Exception as exc:
        _LOGGER.error("Login unexpected error: %s", exc, exc_info=True)
        return None, None, f"异常: {exc}"


class MercurySwitchAPI:
    """API client for Mercury SE109P Pro PoE switch."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ):
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self._cookie_str: str | None = None
        self._tid: int | None = None
        self._last_login: datetime | None = None

    async def close(self):
        """No-op for compatibility."""
        pass

    async def login(self) -> bool:
        """Authenticate to the switch. Returns True on success.

        Uses synchronous urllib in a thread executor to avoid
        aiohttp compatibility issues inside HA.
        """
        loop = asyncio.get_running_loop()
        cookie_str, tid, error_msg = await loop.run_in_executor(
            None,
            _do_login_sync,
            self.base_url.replace("http://", ""),
            self.username,
            self.password,
        )
        if error_msg:
            _LOGGER.error("Login failed: %s", error_msg)

        if cookie_str and tid is not None:
            self._cookie_str = cookie_str
            self._tid = tid
            self._last_login = datetime.now()
            return True
        return False

    async def _ensure_logged_in(self) -> bool:
        """Ensure we have a valid session, re-login if needed."""
        if not self._cookie_str or not self._tid:
            return await self.login()
        if self._last_login and (datetime.now() - self._last_login) > timedelta(minutes=10):
            return await self.login()
        return True

    async def _fetch_page(self, path: str) -> str | None:
        """Fetch a page synchronously in executor."""
        if not await self._ensure_logged_in():
            return None

        for attempt in range(2):
            try:
                loop = asyncio.get_running_loop()
                html = await loop.run_in_executor(
                    None,
                    self._do_fetch_sync,
                    path,
                )
            except Exception as exc:
                _LOGGER.error("Fetch error %s: %s", path, exc)
                if attempt == 0 and await self.login():
                    continue
                return None

            if html is None:
                if attempt == 0 and await self.login():
                    continue
                return None

            # Check for session expiry (login page returned instead of admin page)
            if "logonInfo" in html and "g_tid" not in html:
                _LOGGER.debug("Session expired, re-logging in")
                if attempt == 0 and await self.login():
                    continue
                return None

            # Update tid from page
            tid_match = re.search(r"(?:\bvar\s+)?\bg_tid\s*=\s*(\d+);", html)
            if tid_match:
                self._tid = int(tid_match.group(1))

            return html

        return None

    def _do_fetch_sync(self, path: str) -> str | None:
        """Synchronous page fetch using urllib."""
        import urllib.request

        try:
            req = urllib.request.Request(
                f"{self.base_url}{path}",
                headers={"Cookie": self._cookie_str} if self._cookie_str else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode()
        except Exception as exc:
            _LOGGER.error("Sync fetch error %s: %s", path, exc)
            return None

    def _do_post_sync(self, path: str, data: dict[str, str]) -> bool:
        """Synchronous form POST using urllib."""
        import urllib.request
        import urllib.parse

        if "token" not in data and self._tid is not None:
            data["token"] = str(self._tid)

        try:
            encoded = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(
                f"{self.base_url}{path}",
                data=encoded,
                headers={"Cookie": self._cookie_str} if self._cookie_str else {},
            )
            with urllib.request.urlopen(req, timeout=10):
                return True
        except Exception as exc:
            _LOGGER.error("Sync post error %s: %s", path, exc)
            return False

    async def _post_form(self, path: str, data: dict[str, str]) -> bool:
        """POST form data with session cookie."""
        # Refresh tid first
        await self._fetch_page("/PoeConfigRpm.htm")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._do_post_sync, path, data)

    @staticmethod
    def _extract_json_var(html: str, var_name: str) -> dict | None:
        """Extract a JavaScript object from HTML, handling unquoted JS keys."""
        obj_match = re.search(
            rf"var\s+{re.escape(var_name)}\s*=\s*(\{{.+?\}})\s*;", html, re.DOTALL
        )
        if obj_match:
            raw = obj_match.group(1)
            converted = re.sub(r"([{,]\s*)(\w+)(\s*:)", r'\1"\2"\3', raw)
            converted = re.sub(r",\s*}", "}", converted)
            converted = re.sub(r",\s*]", "]", converted)
            try:
                return json.loads(converted)
            except json.JSONDecodeError as exc:
                _LOGGER.debug("Failed to parse object %s: %s", var_name, exc)

        arr_match = re.search(
            rf"var\s+{re.escape(var_name)}\s*=\s*(\[.+?\])\s*;", html, re.DOTALL
        )
        if arr_match:
            raw = arr_match.group(1)
            converted = re.sub(r",\s*]", "]", raw)
            try:
                return json.loads(converted)
            except json.JSONDecodeError:
                pass

        return None

    async def get_poe_status(self) -> dict | None:
        """Fetch PoE status data from the switch."""
        html = await self._fetch_page("/PoeConfigRpm.htm")
        if not html:
            return None

        result: dict = {}

        global_config = self._extract_json_var(html, "globalConfig")
        if global_config:
            result["global"] = {
                "total_power": global_config.get("system_power_limit", 0) / 10,
                "used_power": global_config.get("system_power_consumption", 0) / 10,
                "remaining_power": global_config.get("system_power_remain", 0) / 10,
                "power_limit_min": global_config.get("system_power_limit_min", 0) / 10,
                "power_limit_max": global_config.get("system_power_limit_max", 0) / 10,
            }

        port_config = self._extract_json_var(html, "portConfig")
        if port_config:
            state = port_config.get("state", [])
            power = port_config.get("power", [])
            current = port_config.get("current", [])
            voltage = port_config.get("voltage", [])
            pdclass = port_config.get("pdclass", [])
            powerstatus = port_config.get("powerstatus", [])
            priority = port_config.get("priority", [])
            powerlimit = port_config.get("powerlimit", [])
            fastpoe = port_config.get("fastpoe", [])
            pptlpoe = port_config.get("pptlpoe", [])

            ports = []
            for i in range(POE_PORT_COUNT):
                ports.append({
                    "port": i + 1,
                    "enabled": bool(state[i]) if i < len(state) else False,
                    "power_w": (power[i] / 10) if i < len(power) and power[i] else 0.0,
                    "current_ma": current[i] if i < len(current) else 0,
                    "voltage_v": (voltage[i] / 10) if i < len(voltage) and voltage[i] else 0.0,
                    "pd_class": pdclass[i] if i < len(pdclass) else 5,
                    "power_status": powerstatus[i] if i < len(powerstatus) else 0,
                    "priority": priority[i] if i < len(priority) else 2,
                    "power_limit": (
                        (powerlimit[i] / 10)
                        if i < len(powerlimit) and powerlimit[i] and powerlimit[i] != 330
                        else 30.0 if i < len(powerlimit) and powerlimit[i] == 330
                        else 0.0
                    ),
                    "fast_poe": bool(fastpoe[i]) if i < len(fastpoe) else False,
                    "permanent_poe": bool(pptlpoe[i]) if i < len(pptlpoe) else False,
                })
            result["ports"] = ports

        return result

    async def get_port_status(self) -> dict | None:
        """Fetch Ethernet port link status."""
        html = await self._fetch_page("/PortSettingRpm.htm")
        if not html:
            return None

        all_info = self._extract_json_var(html, "all_info")
        if not all_info:
            return None

        state = all_info.get("state", [])
        spd_act = all_info.get("spd_act", [])
        fc_cfg = all_info.get("fc_cfg", [])
        fc_act = all_info.get("fc_act", [])
        trunk_info = all_info.get("trunk_info", [])
        port_type = all_info.get("port_type", [])

        ports = []
        for i in range(ETH_PORT_COUNT):
            ports.append({
                "port": i + 1,
                "enabled": bool(state[i]) if i < len(state) else False,
                "speed_actual": spd_act[i] if i < len(spd_act) else 0,
                "flow_control_config": bool(fc_cfg[i]) if i < len(fc_cfg) else False,
                "flow_control_actual": bool(fc_act[i]) if i < len(fc_act) else False,
                "trunk_group": trunk_info[i] if i < len(trunk_info) else 0,
                "port_type": port_type[i] if i < len(port_type) else 0,
            })

        return {"ports": ports}

    async def set_poe_port_state(self, port: int, enable: bool) -> bool:
        """Enable or disable PoE on a specific port."""
        state_val = 1 if enable else 0
        return await self._post_form(
            "/poe_port_config.cgi",
            {f"sel_{port}": "1", "name_pstate": str(state_val + 1)},
        )

    async def power_cycle_port(self, port: int) -> bool:
        """Power cycle a PoE port."""
        return await self._post_form(
            "/poe_port_config.cgi",
            {f"reset_{port}": "重新上电"},
        )

    async def get_system_info(self) -> dict | None:
        """Fetch system info from the switch."""
        html = await self._fetch_page("/SystemInfoRpm.htm")
        if not html:
            return None

        info_ds = self._extract_json_var(html, "info_ds")
        if not info_ds:
            return None

        desc = info_ds.get("descriStr", [""])
        return {
            "description": desc[0] if isinstance(desc, list) else desc,
            "mac": info_ds.get("macStr", [""])[0] if isinstance(info_ds.get("macStr"), list) else "",
            "ip": info_ds.get("ipStr", [""])[0],
            "netmask": info_ds.get("netmaskStr", [""])[0],
            "gateway": info_ds.get("gatewayStr", [""])[0],
            "firmware": info_ds.get("firmwareStr", [""])[0],
            "model": info_ds.get("productModel", [""])[0],
            "hardware": info_ds.get("hardwareStr", [""])[0],
        }

    async def get_main_status(self) -> dict | None:
        """Fetch MainRpm.htm for uptime, packet rates, loop status."""
        html = await self._fetch_page("/MainRpm.htm")
        if not html:
            return None

        result: dict = {}

        # Uptime
        info_ds = self._extract_json_var(html, "info_ds")
        if info_ds:
            work_time = info_ds.get("workTime", [""])
            result["uptime"] = work_time[0] if isinstance(work_time, list) else ""

        # Port rates and Poe flags
        port_info = self._extract_json_var(html, "port_info")
        if port_info:
            rx_rate = port_info.get("rx_rate", [])
            tx_rate = port_info.get("tx_rate", [])
            is_poe = port_info.get("is_poe_port", [])
            is_uplink = port_info.get("is_uplink", [])

            ports = []
            for i in range(ETH_PORT_COUNT):
                ports.append({
                    "port": i + 1,
                    "rx_rate": rx_rate[i] if i < len(rx_rate) else 0,
                    "tx_rate": tx_rate[i] if i < len(tx_rate) else 0,
                    "is_poe": bool(is_poe[i]) if i < len(is_poe) else False,
                    "is_uplink": bool(is_uplink[i]) if i < len(is_uplink) else False,
                })
            result["port_rates"] = ports

        # Loop detection status
        loop_match = re.search(r"var\s+loop\s*=\s*(\d+);", html)
        if loop_match:
            result["loop_detected"] = int(loop_match.group(1)) != 0

        loop_conf = self._extract_json_var(html, "loopPortConf")
        if loop_conf:
            result["loop_prevention_enabled"] = bool(
                loop_conf.get("loopbackEnable", 0)
            )

        return result

    async def get_port_statistics(self) -> dict | None:
        """Fetch PortStatisticsRpm.htm for per-port packet counts."""
        html = await self._fetch_page("/PortStatisticsRpm.htm")
        if not html:
            return None

        all_info = self._extract_json_var(html, "all_info")
        if not all_info:
            return None

        pkts = all_info.get("pkts", [])
        state = all_info.get("state", [])
        link_status = all_info.get("link_status", [])

        ports = []
        for i in range(ETH_PORT_COUNT):
            idx = i * 4
            tx_good = pkts[idx] if idx < len(pkts) else 0
            tx_bad = pkts[idx + 1] if idx + 1 < len(pkts) else 0
            rx_good = pkts[idx + 2] if idx + 2 < len(pkts) else 0
            rx_bad = pkts[idx + 3] if idx + 3 < len(pkts) else 0

            ports.append({
                "port": i + 1,
                "enabled": bool(state[i]) if i < len(state) else False,
                "link_status": link_status[i] if i < len(link_status) else 0,
                "tx_good_packets": tx_good,
                "tx_bad_packets": tx_bad,
                "rx_good_packets": rx_good,
                "rx_bad_packets": rx_bad,
            })

        return {"ports": ports}

    async def get_loop_prevention(self) -> dict | None:
        """Fetch loop prevention config."""
        html = await self._fetch_page("/LoopPreventionRpm.htm")
        if not html:
            return None

        lp_match = re.search(r"var\s+lpEn\s*=\s*(\d+);", html)
        return {"enabled": bool(int(lp_match.group(1))) if lp_match else False}

    async def set_loop_prevention(self, enable: bool) -> bool:
        """Enable or disable loop prevention."""
        return await self._post_form(
            "/loop_prevention_set.cgi",
            {"lpEn": "1" if enable else "0"},
        )
