import subprocess
from pathlib import Path

if __name__ == "__main__":
    frontend_directory = Path(__file__).resolve().parent / "frontend"
    process = subprocess.Popen(
        [
            "node",
            "node_modules/vite/bin/vite.js",
            "--host", "127.0.0.1",
            "--port", "5173",
            "--strictPort",
        ],
        cwd=frontend_directory,
    )
    try:
        exit_code = process.wait()
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait()
    raise SystemExit(exit_code)
