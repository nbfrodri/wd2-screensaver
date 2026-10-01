"""Live data from this machine for the screensavers.

Everything runs in daemon threads and fails soft: if a source is missing the
value just stays at its default, so modes can always read `DATA.<field>`.

Privacy: notifications are only *counted* (never read), audio is analysed in
memory for a spectrum and never stored, weather uses the same wttr.in source
and location as the Omarchy bar widget. Each source can be turned off in the
config file.
"""

import atexit
import ctypes
import json
import math
import os
import random
import shutil
import signal
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import unicodedata

import config

HOME = os.path.expanduser("~")


def display_text(value):
    """Keep external labels to one printable terminal cell per character."""
    value = unicodedata.normalize("NFC", str(value))
    return "".join(c if unicodedata.east_asian_width(c) not in ("W", "F")
                   and unicodedata.category(c)[0] not in ("C", "M") else "?"
                   for c in value)


class SysData:
    def __init__(self):
        self.started = time.time()
        self.cpu = 0.0          # 0..1
        self.mem = 0.0          # 0..1
        self.net_rx = 0.0       # bytes/s
        self.net_tx = 0.0
        self.track = None       # {"title", "artist", "playing"}
        self.notifications = 0
        self.weather = None     # {"temp_c", "desc", "code", "rain", "night"}
        self.bands = [0.0] * 16  # audio spectrum 0..1
        self.level = 0.0         # overall loudness 0..1
        self.beat = 0.0          # decays from 1 after each detected beat
        self.audio_live = False
        self._procs = []
        self._idle_base = self._read_idle_timeout()
        self._lock = threading.Lock()

    # -------------------------------------------------------------- public helpers
    @property
    def idle_seconds(self):
        return self._idle_base + (time.time() - self.started)

    def idle_clock(self):
        s = int(self.idle_seconds)
        return "%02d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60)

    def hour(self):
        t = time.localtime()
        return t.tm_hour + t.tm_min / 60

    def daylight(self):
        """0 = deep night, 1 = noon (simple cosine curve around 13:00)."""
        return max(0.0, math.cos((self.hour() - 13) / 12 * math.pi)) ** 0.7

    def now_playing(self):
        t = self.track
        if t and t.get("title"):
            return display_text("%s - %s" % (t.get("artist") or "?", t["title"]))
        return None

    def band(self, i, n=None):
        """Spectrum value for bar i out of n bars (resampled from 16 bands)."""
        n = n or len(self.bands)
        j = min(len(self.bands) - 1, int(i * len(self.bands) / max(1, n)))
        return self.bands[j]

    # -------------------------------------------------------------- start
    def start(self):
        cfg = config.CFG
        if cfg["data"]["stats"]:
            self._thread(self._stats_loop)
        if cfg["data"]["music"]:
            self._thread(self._mpris_loop)
        if cfg["data"]["notifications"]:
            self._thread(self._notif_loop)
        if cfg["data"]["weather"]:
            self._thread(self._weather_loop)
        self._thread(self._fake_audio_loop)
        if cfg["data"]["audio"] and shutil.which("parec"):
            self._thread(self._audio_loop)
        atexit.register(self.stop)
        return self

    def stop(self):
        for p in self._procs:
            try:
                p.kill()
            except Exception:
                pass

    @staticmethod
    def _thread(fn):
        threading.Thread(target=fn, daemon=True).start()

    # -------------------------------------------------------------- sources
    @staticmethod
    def _read_idle_timeout():
        try:
            with open(os.path.join(HOME, ".config/omarchy/shell.json")) as f:
                return float(json.load(f).get("idle", {}).get("screensaver", 150))
        except Exception:
            return 150.0

    def _stats_loop(self):
        def cpu_times():
            with open("/proc/stat") as f:
                v = [int(x) for x in f.readline().split()[1:]]
            return sum(v), v[3] + v[4]

        def net_bytes():
            rx = tx = 0
            with open("/proc/net/dev") as f:
                for line in f.readlines()[2:]:
                    name, data = line.split(":", 1)
                    if name.strip() == "lo":
                        continue
                    d = data.split()
                    rx += int(d[0])
                    tx += int(d[8])
            return rx, tx

        last_cpu, last_net, last_t = cpu_times(), net_bytes(), time.time()
        while True:
            time.sleep(1.0)
            try:
                c, n, t = cpu_times(), net_bytes(), time.time()
                dt_total = c[0] - last_cpu[0]
                if dt_total:
                    self.cpu = 1 - (c[1] - last_cpu[1]) / dt_total
                dt = max(0.01, t - last_t)
                self.net_rx = (n[0] - last_net[0]) / dt
                self.net_tx = (n[1] - last_net[1]) / dt
                last_cpu, last_net, last_t = c, n, t
                mem = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        k, v = line.split(":")
                        mem[k] = int(v.split()[0])
                self.mem = 1 - mem.get("MemAvailable", 0) / max(1, mem.get("MemTotal", 1))
            except Exception:
                pass

    def _mpris_loop(self):
        while True:
            try:
                names = subprocess.run(["busctl", "--user", "--json=short", "list"], capture_output=True,
                                       text=True, timeout=3).stdout
                players = [n["name"] for n in json.loads(names) if n.get("name", "").startswith("org.mpris.MediaPlayer2.")]
                track = None
                for name in players:
                    def prop(p):
                        r = subprocess.run(["busctl", "--user", "--json=short", "get-property", name,
                                            "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", p],
                                           capture_output=True, text=True, timeout=3)
                        return json.loads(r.stdout)["data"] if r.returncode == 0 else None
                    status = prop("PlaybackStatus")
                    meta = prop("Metadata") or {}
                    title = (meta.get("xesam:title") or {}).get("data")
                    artists = (meta.get("xesam:artist") or {}).get("data") or []
                    if title:
                        cand = {"title": title, "artist": ", ".join(artists), "playing": status == "Playing"}
                        if track is None or cand["playing"]:
                            track = cand
                self.track = track
            except Exception:
                pass
            time.sleep(3)

    def _notif_loop(self):
        path = os.path.join(HOME, ".local/state/omarchy/notifications/history")
        while True:
            try:
                self.notifications = len([f for f in os.listdir(path) if f.endswith(".json")])
            except Exception:
                pass
            time.sleep(10)

    def _weather_loop(self):
        cache = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "wd2-screensaver-weather.json")
        while True:
            data = None
            try:
                if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 1800:
                    with open(cache) as f:
                        data = json.load(f)
                else:
                    loc = ""
                    try:
                        with open(os.path.join(HOME, ".local/state/omarchy/settings/weather.json")) as f:
                            st = json.load(f)
                        if st.get("latitude") is not None and st.get("longitude") is not None:
                            loc = "%s,%s" % (st["latitude"], st["longitude"])
                        elif st.get("location"):
                            loc = urllib.parse.quote(str(st["location"]))
                    except Exception:
                        pass
                    req = urllib.request.Request("https://wttr.in/%s?format=j1" % loc, headers={"User-Agent": "curl/8"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.load(r)
                    with open(cache, "w") as f:
                        json.dump(data, f)
                cur = data["current_condition"][0]
                code = int(cur.get("weatherCode", 113))
                self.weather = {
                    "temp_c": int(cur.get("temp_C", 0)),
                    "desc": display_text(cur.get("weatherDesc", [{}])[0].get("value", "")),
                    "code": code,
                    "rain": code in (176, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359, 386, 389),
                    "fog": code in (143, 248, 260),
                    "clouds": code in (116, 119, 122),
                }
            except Exception:
                pass
            time.sleep(1800 if data else 120)

    def _audio_loop(self):
        try:
            import numpy as np
        except Exception:
            return
        rate, chunk = 22050, 1024

        def pdeathsig():
            try:
                ctypes.CDLL("libc.so.6").prctl(1, signal.SIGKILL)
            except Exception:
                pass

        try:
            proc = subprocess.Popen(["parec", "--device=@DEFAULT_MONITOR@", "--format=s16le", "--rate=%d" % rate,
                                     "--channels=1", "--latency-msec=40", "--raw"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, preexec_fn=pdeathsig)
        except Exception:
            return
        self._procs.append(proc)
        edges = np.geomspace(40, 9000, 17)
        freqs = np.fft.rfftfreq(chunk, 1 / rate)
        idx = [np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0] for i in range(16)]
        win = np.hanning(chunk)
        peak = np.full(16, 1e-3)
        energy_hist = []
        smooth = np.zeros(16)
        while True:
            raw = proc.stdout.read(chunk * 2)
            if not raw or len(raw) < chunk * 2:
                break
            x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            spec = np.abs(np.fft.rfft(x * win))
            b = np.array([spec[i].mean() if len(i) else 0.0 for i in idx])
            peak = np.maximum(peak * 0.995, b)
            norm = np.clip(b / np.maximum(peak, 1e-3), 0, 1) * np.clip(np.sqrt(b.sum()) * 0.6, 0, 1)
            smooth = np.maximum(norm, smooth * 0.82)
            rms = float(np.sqrt(np.mean(x * x)))
            self.audio_live = rms > 0.003
            if not self.audio_live:
                continue
            self.bands = smooth.tolist()
            self.level = min(1.0, rms * 4)
            e = float(b[:4].sum())
            energy_hist = (energy_hist + [e])[-43:]
            avg = sum(energy_hist) / len(energy_hist)
            if e > avg * 1.5 and e > 0.5 and self.beat < 0.5:
                self.beat = 1.0
            else:
                self.beat *= 0.88
        self.audio_live = False

    def _fake_audio_loop(self):
        """Pleasant procedural motion when there is no audio."""
        t0 = time.time()
        while True:
            t = time.time() - t0
            if not self.audio_live:
                self.bands = [max(0.0, 0.35 + 0.3 * math.sin(t * (1.3 + i * 0.21) + i) + random.uniform(-0.1, 0.1)) * (1 - i / 24)
                              for i in range(16)]
                self.level = 0.3 + 0.2 * math.sin(t * 2)
                self.beat = 1.0 if (t % 0.6) < 0.05 else self.beat * 0.85
            time.sleep(0.04)


DATA = SysData()
