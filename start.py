#!/usr/bin/env python3
import os
import sys
import time
import signal
import socket
import threading
import subprocess
import webbrowser

ROOT      = os.path.dirname(os.path.abspath(__file__))
BACKEND   = os.path.join(ROOT, 'backend')
FRONTEND  = os.path.join(ROOT, 'frontend')
ML        = os.path.join(ROOT, 'ml')

BACKEND_PORT  = 5000
FRONTEND_PORT = 8080

class C:
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    CYAN   = '\033[96m'
    RED    = '\033[91m'
    DIM    = '\033[2m'

def banner():
    print(f"""
{C.RESET}{C.DIM}  Smart Agriculture Digital Twin  —  v1.0{C.RESET}
""")

def log(tag, msg, color=C.RESET):
    print(f"{C.DIM}[{C.RESET}{color}{C.BOLD}{tag}{C.RESET}{C.DIM}]{C.RESET} {msg}")

def ok(msg):   print(f"{C.GREEN}✓ {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}⚠ {msg}{C.RESET}")
def err(msg):  print(f"{C.RED}✗ {msg}{C.RESET}")

# ── Port utilities ────────────────────────────────────────────────────────────

def is_port_free(port: int) -> bool:
    """Return True if the port is not in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex(('127.0.0.1', port)) != 0

def free_port(port: int):
    """Kill whatever process is holding the port."""
    try:
        result = subprocess.run(
            ['lsof', '-t', f'-i:{port}'],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            pid = pid.strip()
            if pid.isdigit():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    warn(f'Killed PID {pid} holding port {port}')
                except ProcessLookupError:
                    pass
        time.sleep(0.8)  # give OS time to release the port
    except FileNotFoundError:
        # lsof not available — try fuser
        subprocess.run(['fuser', '-k', f'{port}/tcp'],
                       capture_output=True)
        time.sleep(0.8)

def ensure_port_free(port: int, name: str):
    """Check port and kill occupant if needed. Exit if still blocked."""
    if is_port_free(port):
        return
    warn(f'Port {port} is in use — freeing it…')
    free_port(port)
    if not is_port_free(port):
        err(f'Could not free port {port} for {name}. '
            f'Run manually: fuser -k {port}/tcp')
        sys.exit(1)
    ok(f'Port {port} is now free')

# ── Package checks ────────────────────────────────────────────────────────────

def install_requirements():
    log('SETUP', 'Checking Python packages…', C.CYAN)
    required = {
        'flask':        'flask',
        'flask_cors':   'flask-cors',
        'sklearn':      'scikit-learn',
        'pandas':       'pandas',
        'numpy':        'numpy',
        'firebase_admin': 'firebase-admin',
    }
    missing = [pkg for mod, pkg in required.items() if not _can_import(mod)]
    if not missing:
        ok('All packages installed')
        return
    log('SETUP', f'Installing: {", ".join(missing)}', C.YELLOW)
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--quiet'] + missing,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err(f'pip install failed:\n{result.stderr}')
        err('Run manually: pip install -r requirements.txt')
        sys.exit(1)
    ok(f'Installed: {", ".join(missing)}')

def _can_import(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False

# ── Pre-flight ────────────────────────────────────────────────────────────────

def preflight():
    log('CHECK', 'Pre-flight checks…', C.CYAN)

    cfg_path = os.path.join(ROOT, 'config', 'firebase_admin.json')
    if not os.path.exists(cfg_path):
        warn('config/firebase_admin.json missing — Firebase will not work')
        warn('Download: Firebase Console → Project Settings → Service Accounts → Generate new private key')
    else:
        import json
        with open(cfg_path) as f:
            cfg = json.load(f)
        if cfg.get('project_id', 'your-project-id').startswith('your-'):
            warn('config/firebase_admin.json contains placeholder values — replace with real credentials')
        else:
            ok('Firebase admin config found')

    db_url = os.environ.get('FIREBASE_DB_URL', '')
    if not db_url:
        warn('FIREBASE_DB_URL not set')
        warn('Run: export FIREBASE_DB_URL=https://YOUR_PROJECT-default-rtdb.firebaseio.com')
    else:
        ok(f'FIREBASE_DB_URL = {db_url}')

    model_path = os.path.join(ML, 'model.pkl')
    if not os.path.exists(model_path):
        warn('No model.pkl — click Train Model in the dashboard or run: python -m ml.train_model')
    else:
        ok('model.pkl found')

    csv_path = os.path.join(ROOT, 'data', 'sensor_data.csv')
    if os.path.exists(csv_path):
        ok('Dataset: data/sensor_data.csv')
    else:
        warn('No dataset CSV — synthetic data will be used for training')

    glb_path = os.path.join(FRONTEND, 'assets', 'farm.glb')
    if os.path.exists(glb_path):
        ok(f'Farm model: frontend/assets/farm.glb ({os.path.getsize(glb_path) // 1024 // 1024}MB)')
    else:
        warn('No farm.glb found at frontend/assets/farm.glb')

# ── Process launchers ─────────────────────────────────────────────────────────

def stream_output(proc, tag, color):
    for line in iter(proc.stdout.readline, ''):
        line = line.rstrip()
        if line:
            print(f"{C.DIM}[{C.RESET}{color}{tag}{C.RESET}{C.DIM}]{C.RESET} {C.DIM}{line}{C.RESET}")

def start_backend():
    ensure_port_free(BACKEND_PORT, 'Flask backend')
    log('START', f'Flask backend  → http://localhost:{BACKEND_PORT}', C.GREEN)
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{BACKEND}{os.pathsep}{ML}"
    env['PORT']       = str(BACKEND_PORT)
    proc = subprocess.Popen(
        [sys.executable, '-u', 'app.py'],
        cwd=BACKEND, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    threading.Thread(target=stream_output, args=(proc, 'FLASK', C.GREEN), daemon=True).start()
    return proc

def start_frontend():
    ensure_port_free(FRONTEND_PORT, 'Frontend server')
    log('START', f'Frontend       → http://localhost:{FRONTEND_PORT}', C.CYAN)
    proc = subprocess.Popen(
        [sys.executable, '-u', '-m', 'http.server', str(FRONTEND_PORT), '--directory', FRONTEND],
        cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    threading.Thread(target=stream_output, args=(proc, 'HTTP ', C.CYAN), daemon=True).start()
    return proc

def open_browser():
    time.sleep(1.8)
    try:
        webbrowser.open(f'http://localhost:{FRONTEND_PORT}')
    except Exception:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    banner()
    processes = []

    def shutdown(sig=None, frame=None):
        print(f"\n{C.YELLOW}Shutting down AgroTwin…{C.RESET}")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        ok('Stopped.')
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    install_requirements()
    preflight()

    print()
    backend_proc  = start_backend()
    frontend_proc = start_frontend()
    processes.extend([backend_proc, frontend_proc])

    threading.Thread(target=open_browser, daemon=True).start()

    print()
    print(f"{C.GREEN}{C.BOLD}══════════════════════════════════════════{C.RESET}")
    print(f"{C.GREEN}{C.BOLD}  AgroTwin is running!{C.RESET}")
    print(f"{C.GREEN}  Dashboard  →  http://localhost:{FRONTEND_PORT}{C.RESET}")
    print(f"{C.GREEN}  API        →  http://localhost:{BACKEND_PORT}{C.RESET}")
    print(f"{C.GREEN}{C.BOLD}  Press Ctrl+C to stop{C.RESET}")
    print(f"{C.GREEN}{C.BOLD}══════════════════════════════════════════{C.RESET}")
    print()

    # ── Watch loop — restart crashed processes, always clearing port first ──
    while True:
        time.sleep(2)

        if backend_proc.poll() is not None:
            code = backend_proc.returncode
            err(f'Flask crashed (exit {code}) — restarting in 3s…')
            time.sleep(3)
            backend_proc  = start_backend()   # ensure_port_free called inside
            processes[0]  = backend_proc

        if frontend_proc.poll() is not None:
            err('Frontend crashed — restarting in 3s…')
            time.sleep(3)
            frontend_proc = start_frontend()  # ensure_port_free called inside
            processes[1]  = frontend_proc

if __name__ == '__main__':
    main()