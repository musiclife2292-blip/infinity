"""Source and PyInstaller entry point. No network access on startup."""
from multiprocessing import freeze_support
from infinity_audio.app import main

if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
