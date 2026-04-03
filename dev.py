"""
Dev runner - watches .py files and restarts the bot on changes.
Usage: python dev.py
"""

import subprocess
import sys
import time
import signal
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BOT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
WATCH_EXTENSIONS = {".py"}
DEBOUNCE_SECONDS = 1.0


class BotProcess:
    def __init__(self):
        self.process = None

    def start(self):
        print(f"\n{'='*50}")
        print("Starting bot...")
        print(f"{'='*50}\n")
        self.process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

    def stop(self):
        if self.process and self.process.poll() is None:
            print("\nStopping bot...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def restart(self):
        self.stop()
        self.start()


class ReloadHandler(FileSystemEventHandler):
    def __init__(self, bot: BotProcess):
        self.bot = bot
        self._last_reload = 0

    def on_modified(self, event):
        self._maybe_reload(event.src_path)

    def on_created(self, event):
        self._maybe_reload(event.src_path)

    def _maybe_reload(self, path):
        if event_is_relevant(path) and self._debounce():
            print(f"\nFile changed: {os.path.relpath(path)}")
            self.bot.restart()

    def _debounce(self):
        now = time.time()
        if now - self._last_reload < DEBOUNCE_SECONDS:
            return False
        self._last_reload = now
        return True


def event_is_relevant(path):
    _, ext = os.path.splitext(path)
    if ext not in WATCH_EXTENSIONS:
        return False
    # Ignore __pycache__ and hidden dirs
    parts = path.split(os.sep)
    if any(p.startswith(".") or p == "__pycache__" for p in parts):
        return False
    return True


def main():
    bot = BotProcess()
    bot.start()

    watch_dir = os.path.dirname(os.path.abspath(__file__))
    handler = ReloadHandler(bot)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=True)
    observer.start()

    print(f"Watching {watch_dir} for .py changes...")

    def shutdown(signum, frame):
        print("\nShutting down...")
        observer.stop()
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            # Also restart if the bot crashes
            if bot.process.poll() is not None:
                exit_code = bot.process.returncode
                if exit_code != 0:
                    print(f"\nBot exited with code {exit_code}, restarting in 3s...")
                    time.sleep(3)
                    bot.start()
                else:
                    print("\nBot exited cleanly.")
                    break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        bot.stop()


if __name__ == "__main__":
    main()
