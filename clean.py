import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# Target directory names and file patterns to remove
DIR_PATTERNS = ["__pycache__", ".pytest_cache", ".mypy_cache", ".coverage", "build", "dist", "*.egg-info"]
FILE_PATTERNS = ["*.pyc", "*.pyo", "*.tmp", "*.swp", "*.log"]

def clean_repo():
    removed_dirs = 0
    removed_files = 0

    print("🧹 Sweeping repository clutter...")

    # Remove matching directories recursively
    for pattern in DIR_PATTERNS:
        for target in PROJECT_ROOT.rglob(pattern):
            if target.is_dir():
                try:
                    shutil.rmtree(target)
                    print(f"  [REMOVED DIR]  {target.relative_to(PROJECT_ROOT)}")
                    removed_dirs += 1
                except Exception as e:
                    print(f"  [ERROR] Could not remove {target}: {e}")

    # Remove matching files recursively
    for pattern in FILE_PATTERNS:
        for target in PROJECT_ROOT.rglob(pattern):
            if target.is_file():
                try:
                    target.unlink()
                    print(f"  [REMOVED FILE] {target.relative_to(PROJECT_ROOT)}")
                    removed_files += 1
                except Exception as e:
                    print(f"  [ERROR] Could not remove {target}: {e}")

    print(f"\n✨ Clean complete: Removed {removed_dirs} folders and {removed_files} files.\n")

if __name__ == "__main__":
    clean_repo()