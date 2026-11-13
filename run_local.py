#!/usr/bin/env python3
"""Run facts on this computer only.

Builds the page now and every 15 minutes, and serves it at http://127.0.0.1:8765
(reachable from this computer only). Close the window or press Ctrl+C to stop.

Starting it again replaces a copy that is already running, so the desktop shortcut also restarts.
Updates need no reinstall: when build.py, rules/ or site/ change on disk the tests are run and,
if they pass, the page is rebuilt within seconds; when this file changes the program restarts
itself (start.bat loops on exit code 3). Everything printed here is also kept in out/run.log.
"""
import functools, http.server, importlib, json, os, subprocess, sys, threading, time, traceback
import urllib.request, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8765"))
EVERY = int(os.environ.get("EVERY_SECONDS", "900"))
ONCE = os.environ.get("ONCE") == "1"
RESTART_CODE = 3
WATCH = ["build.py", "test_build.py", "rules", "site"]
quit_now = threading.Event()


class Tee:
    """Console output that is also appended to a log file."""
    def __init__(self, stream, path):
        self.stream, self.path = stream, path

    def write(self, text):
        try:
            self.stream.write(text)
        except Exception:
            pass
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass
        return len(text)

    def flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass


def start_log(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "run.log")
    try:                                   # keep the tail of the previous log
        with open(path, "rb") as f:
            tail = f.read()[-60000:]
        with open(path, "wb") as f:
            f.write(tail)
    except OSError:
        pass
    sys.stdout, sys.stderr = Tee(sys.stdout, path), Tee(sys.stderr, path)
    print("\n==== started", time.strftime("%Y-%m-%d %H:%M:%S"), "====")


def stamp(paths):
    """Newest modification time under the given files and folders."""
    newest = 0.0
    for p in paths:
        p = os.path.join(HERE, p)
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    try:
                        newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                    except OSError:
                        pass
        elif os.path.exists(p):
            newest = max(newest, os.path.getmtime(p))
    return newest


def tests_pass():
    """Run the rule tests in a separate process. An update that breaks a rule is not applied."""
    if not os.path.exists(os.path.join(HERE, "test_build.py")):
        return True
    try:
        env = {k: v for k, v in os.environ.items()
               if k not in ("SELF_HEAL", "AI", "MIN_OUTLETS", "NEW_MIN_SCORE", "MIN_SPREAD", "NAME_MIN")}
        r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", "-q", "test_build"],
                           cwd=HERE, capture_output=True, text=True, timeout=120, env=env)
    except Exception as e:
        print("could not run the tests:", repr(e))
        return False
    if r.returncode != 0:
        print("TESTS FAILED, update not applied:\n" + (r.stderr or r.stdout)[-1500:])
    return r.returncode == 0


def next_slot():
    """3 minutes after the next quarter hour, when the news batch for it is normally out."""
    return time.time() - time.time() % EVERY + EVERY + 180


def data_until(out_dir):
    try:
        with open(os.path.join(out_dir, "data.json"), encoding="utf-8") as f:
            return json.load(f).get("data_until")
    except Exception:
        return None


def build_once(build):
    try:
        build.main()
        return True
    except SystemExit as e:                # build.py stops itself rather than publish bad data
        print("update skipped:", e)
    except Exception:
        traceback.print_exc()
        print("update failed; the last good page stays up")
    return False


def ensure_shortcut():
    """Put a "facts" shortcut with the icon on the Windows desktop. Clicking it starts facts,
    or restarts it if it is already running. Anything that goes wrong is written to the log."""
    if os.name != "nt":
        return
    q = lambda p: os.path.join(HERE, p).replace("'", "''")
    # The shortcut runs facts.vbs, which starts the program with no window to close by accident.
    script = ("$d = [Environment]::GetFolderPath('Desktop'); $p = Join-Path $d 'news.lnk'; "
              "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
              "$s.TargetPath = (Join-Path $env:WINDIR 'System32\\wscript.exe'); "
              "$s.Arguments = '\"%s\"'; $s.WorkingDirectory = '%s'; $s.IconLocation = '%s,0'; "
              "$s.Description = 'Start or restart news'; $s.Save(); Remove-Item (Join-Path $d 'facts.lnk') -ErrorAction SilentlyContinue; Write-Output $p"
              % (q("facts.vbs"), HERE.replace("'", "''"), q("icon.ico")))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        print("desktop shortcut:", out if r.returncode == 0 and out else "FAILED " + (r.stderr or out)[-600:])
    except Exception as e:
        print("desktop shortcut: FAILED", repr(e))


_keep = []


def log_console_events():
    """Windows: write to the log why the program is being ended (window closed, logoff, shutdown),
    so a stop is never a mystery."""
    if os.name != "nt":
        return
    try:
        import ctypes
        names = {0: "Ctrl+C", 1: "Ctrl+Break", 2: "the window was closed", 5: "logoff", 6: "shutdown"}

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
        def handler(event):
            print("ending:", names.get(event, "console event %d" % event), time.strftime("%H:%M:%S"))
            return 0                        # let Windows carry on with the default action

        _keep.append(handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, 1)
    except Exception as e:
        print("could not watch console events:", repr(e))


def take_over():
    """If a copy is already serving the port, ask it to stop and wait until it has (it may be in
    the middle of an update); stop it by force only if it does not go."""
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/__quit" % PORT, timeout=3).read()
        print("asked the running copy to stop")
    except Exception:
        pass
    for _ in range(90):
        if not port_answers():
            return
        time.sleep(2)
    if os.name == "nt":
        print("the running copy did not stop; ending it")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | "
                        "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" % PORT],
                       capture_output=True, timeout=30)
        time.sleep(2)


class OneServer(http.server.ThreadingHTTPServer):
    # On Windows "reuse address" lets a second copy bind the same port and run alongside the
    # first; two copies then overwrite each other's files. Never allow it.
    allow_reuse_address = os.name != "nt"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/__quit":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"news has stopped. Start it again with the news shortcut on the desktop.")
            quit_now.set()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def port_answers():
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/how.html" % PORT, timeout=2).read(1)
        return True
    except Exception:
        return False


def go_background():
    """Windows: when started in a visible window, start again without one and let this window
    close, so there is no window to close by accident. Returns True if that worked."""
    vbs = os.path.join(HERE, "facts.vbs")
    if os.name != "nt" or os.environ.get("PF_HIDDEN") == "1" or ONCE or not os.path.exists(vbs):
        return False
    if port_answers():
        take_over()                                   # stop the copy that is running
    try:
        subprocess.Popen(["wscript.exe", vbs], cwd=HERE)
    except Exception as e:
        print("could not start in the background:", repr(e))
        return False
    for _ in range(20):
        time.sleep(1)
        if port_answers():
            print("news now runs in the background; this window closes")
            return True
    print("background start did not come up; running in this window instead")
    return False


def serve(out_dir):
    handler = functools.partial(Handler, directory=out_dir)
    for attempt in range(3):
        try:
            return OneServer(("127.0.0.1", PORT), handler)
        except OSError:
            if attempt == 0:
                take_over()
            else:
                time.sleep(3)
    return None


def main():
    os.environ["SELF_HEAL"] = "1"           # a damaged memory file is set aside, not fatal
    import build
    if os.name == "nt":
        os.system("title news")
    start_log(build.OUT)
    log_console_events()
    if go_background():
        return 0
    if ONCE:
        build_once(build)
        return 0
    server = serve(build.OUT)              # serve the last good page while the first update runs
    if server is None:
        print("Port %d is in use and could not be freed. Close the other news window." % PORT)
        return 1
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % PORT
    print("news is at", url, "(running in the background)" if os.environ.get("PF_HIDDEN") == "1"
          else "(keep this window open; close it to stop)")
    ensure_shortcut()
    if os.environ.get("PF_RESTART") != "1":
        webbrowser.open(url)
    self_stamp, code_stamp = stamp(["run_local.py"]), stamp(WATCH)
    if not tests_pass():
        print("warning: the rule tests fail on this copy; running anyway")
    print("updating (a first run looks back 4 hours and can take a few minutes)...")
    build_once(build)
    next_run = next_slot()
    try:
        while not quit_now.wait(5):
            if stamp(["run_local.py"]) != self_stamp:
                time.sleep(3)                          # let the new file finish landing
                print("program updated: restarting")
                server.shutdown()
                server.server_close()
                return RESTART_CODE
            changed = stamp(WATCH)
            if changed != code_stamp:
                time.sleep(3)                          # let a multi-file update finish landing
                code_stamp = stamp(WATCH)
                print(time.strftime("%H:%M"), "files updated: testing...")
                if tests_pass():
                    try:
                        importlib.reload(build)
                        print("update applied: rebuilding...")
                        build_once(build)
                    except Exception:
                        traceback.print_exc()
                        print("update could not be loaded; still running the previous rules")
            elif time.time() >= next_run:
                print(time.strftime("%H:%M"), "updating...")
                before = data_until(build.OUT)
                build_once(build)
                if data_until(build.OUT) == before and time.time() < next_slot() - EVERY + 600:
                    next_run = time.time() + 120           # the new batch is not out yet: try again in 2 min
                else:
                    next_run = next_slot()                 # no pile-up after sleep
    except KeyboardInterrupt:
        pass
    print("stopped")
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
