"""
DevMind Studio — File Manager
Handles all project file system operations.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)


class FileManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_dir = PROJECTS_DIR / project_id
        self.project_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # Core operations
    # ──────────────────────────────────────────────

    def get_file(self, path: str) -> Optional[str]:
        """Read file content. Returns None if not found."""
        file_path = self._resolve(path)
        if file_path and file_path.is_file():
            try:
                return file_path.read_text(encoding="utf-8")
            except Exception:
                return "<binary file — cannot display>"
        return None

    def write_file(self, path: str, content: str) -> bool:
        """Create or overwrite a file, creating parent directories as needed."""
        path = self._sanitize(path)
        if not path:
            return False
        file_path = self.project_dir / path
        # Safety: if path already exists as a directory (from a bad previous run), skip it
        if file_path.is_dir():
            import logging
            logging.getLogger(__name__).warning(
                "Skipping write_file: path exists as directory: %s", file_path
            )
            return False
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return True

    def delete_file(self, path: str) -> bool:
        """Delete a file. Returns True if successful."""
        file_path = self._resolve(path)
        if file_path and file_path.is_file():
            file_path.unlink()
            # Remove empty parent dirs (up to project root)
            try:
                file_path.parent.rmdir()
            except OSError:
                pass
            return True
        return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file within the project."""
        src = self._resolve(old_path)
        new_path = self._sanitize(new_path)
        if not src or not src.is_file() or not new_path:
            return False
        dest = self.project_dir / new_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return True

    # ──────────────────────────────────────────────
    # Listing / context helpers
    # ──────────────────────────────────────────────

    def list_files(self) -> List[Dict]:
        """Return metadata for every file in the project (sorted)."""
        files = []
        for fp in sorted(self.project_dir.rglob("*")):
            if fp.is_file() and not self._is_ignored(fp):
                rel = str(fp.relative_to(self.project_dir)).replace("\\", "/")
                stat = fp.stat()
                files.append({
                    "path": rel,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": fp.suffix.lstrip("."),
                })
        return files

    def get_tree(self) -> Dict:
        """Return a nested directory tree for the file explorer."""
        tree: Dict = {}
        for info in self.list_files():
            parts = info["path"].split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = info["extension"]
        return tree

    def get_all_content(self, max_file_size: int = 8_000) -> Dict[str, str]:
        """Return {path: content} for all text files up to max_file_size chars."""
        result: Dict[str, str] = {}
        for info in self.list_files():
            if info["size"] < max_file_size * 2:  # rough byte estimate
                content = self.get_file(info["path"])
                if content is not None and len(content) <= max_file_size:
                    result[info["path"]] = content
        return result

    def get_project_context(self, max_files: int = 12, max_chars: int = 6_000) -> str:
        """
        Build a compact project context string for Gemini.
        Includes file list and contents (truncated if needed).
        """
        all_files = self.list_files()
        if not all_files:
            return "**Empty project** — no files have been created yet."

        lines = [f"**Project has {len(all_files)} file(s):**\n"]
        for f in all_files:
            lines.append(f"  • {f['path']}  ({f['size']} bytes)")

        lines.append("\n**File Contents:**")
        content_map = self.get_all_content()
        chars_used = 0
        count = 0
        for path, content in content_map.items():
            if count >= max_files or chars_used >= max_chars:
                lines.append(f"\n_(+ {len(content_map) - count} more files not shown)_")
                break
            snippet = content[:max_chars - chars_used]
            lines.append(f"\n### {path}\n```\n{snippet}\n```")
            chars_used += len(snippet)
            count += 1

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────

    def _resolve(self, path: str) -> Optional[Path]:
        """Safely resolve a relative path within the project dir."""
        path = self._sanitize(path)
        if not path:
            return None
        resolved = (self.project_dir / path).resolve()
        # Security: ensure it stays inside the project dir
        try:
            resolved.relative_to(self.project_dir.resolve())
        except ValueError:
            return None
        return resolved

    @staticmethod
    def _sanitize(path: str) -> str:
        """Safely normalize a relative file path, removing traversal and leading dots/slashes."""
        path = path.replace("\\", "/")
        # Remove any traversal attempts and clean up parts
        parts = [p for p in path.split("/") if p and p not in ("..", ".")]
        return "/".join(parts)

    @staticmethod
    def _is_ignored(path: Path) -> bool:
        ignored = {".git", "__pycache__", ".DS_Store", "node_modules", ".env"}
        return any(part in ignored for part in path.parts)