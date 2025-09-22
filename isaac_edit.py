"""New Tkinter-based interface for The Binding of Isaac save editor.

This module provides a refreshed GUI with tab structure and a main tab that
allows users to edit key numeric values such as donation machine totals and
win streaks. It replaces the legacy ``gui.py`` entry point for everyday use
while keeping existing backend logic in ``script.py``.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List

import script


class IsaacSaveEditor(tk.Tk):
    """Main application window for the save editor."""

    MAIN_TAB_NAMES: List[str] = [
        "메인",
        "캐릭터",
        "패시브",
        "액티브",
        "장신구",
        "카드",
        "알약",
        "룬",
        "픽업",
        "보스",
        "기타",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.title("Isaac Savefile Editor")

        self.filename: str = ""
        self.data: bytes | None = None

        self._numeric_config: Dict[str, Dict[str, int | str]] = {
            "donation": {
                "offset": 0x4C,
                "title": "기부 기계 (Donation Machine)",
                "description": "기부 기계",
            },
            "greed": {
                "offset": 0x1B0,
                "title": "그리드 기계 (Greed Machine)",
                "description": "그리드 기계",
            },
            "streak": {
                "offset": 0x54,
                "title": "연승 (Win Streak)",
                "description": "연승",
            },
            "eden": {
                "offset": 0x50,
                "title": "에덴 토큰 (Eden Tokens)",
                "description": "에덴 토큰",
            },
        }
        self._numeric_order: List[str] = ["donation", "greed", "streak", "eden"]

        self._numeric_vars: Dict[str, Dict[str, tk.StringVar]] = {}

        self._build_layout()

    # ------------------------------------------------------------------
    # Layout construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        main_tab = ttk.Frame(notebook, padding=12)
        main_tab.columnconfigure(0, weight=1)
        notebook.add(main_tab, text=self.MAIN_TAB_NAMES[0])

        for tab_name in self.MAIN_TAB_NAMES[1:]:
            placeholder = ttk.Frame(notebook, padding=12)
            notebook.add(placeholder, text=tab_name)

        self._build_main_tab(main_tab)

    def _build_main_tab(self, container: ttk.Frame) -> None:
        top_frame = ttk.Frame(container)
        top_frame.grid(column=0, row=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)

        open_button = ttk.Button(
            top_frame,
            text="아이작 세이브파일 열기",
            command=self.open_save_file,
        )
        open_button.grid(column=0, row=0, sticky="w")

        self.loaded_file_var = tk.StringVar(value="불러온 파일 (Loaded File): 없음")
        loaded_file_label = ttk.Label(top_frame, textvariable=self.loaded_file_var)
        loaded_file_label.grid(column=1, row=0, sticky="w", padx=(10, 0))

        for row_index, key in enumerate(self._numeric_order, start=1):
            config = self._numeric_config[key]
            current_var = tk.StringVar(value="0")
            entry_var = tk.StringVar(value="0")
            self._numeric_vars[key] = {
                "current": current_var,
                "entry": entry_var,
            }
            self._build_numeric_section(
                container=container,
                row=row_index,
                title=str(config["title"]),
                current_var=current_var,
                entry_var=entry_var,
                command=lambda field_key=key: self.apply_field(field_key),
            )

        set_999_button = ttk.Button(
            container,
            text="기부/그리드 기계 999로 설정 (Set Donation & Greed to 999)",
            command=self.set_donation_and_greed_to_max,
        )
        set_999_button.grid(column=0, row=len(self._numeric_order) + 1, sticky="e", pady=(12, 0))

    def _build_numeric_section(
        self,
        container: ttk.Frame,
        row: int,
        title: str,
        current_var: tk.StringVar,
        entry_var: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        section = ttk.LabelFrame(container, text=title, padding=(12, 10))
        pady = (15, 0) if row == 1 else (10, 0)
        section.grid(column=0, row=row, sticky="ew", pady=pady)
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="현재값 (Current):").grid(column=0, row=0, sticky="w")
        ttk.Label(section, textvariable=current_var).grid(column=1, row=0, sticky="w")

        ttk.Label(section, text="새 값 (New Value):").grid(column=0, row=1, sticky="w", pady=(8, 0))
        entry = ttk.Entry(section, textvariable=entry_var, width=12)
        entry.grid(column=1, row=1, sticky="w", pady=(8, 0))

        apply_button = ttk.Button(section, text="적용 (Apply)", command=command)
        apply_button.grid(column=2, row=1, sticky="e", padx=(10, 0), pady=(8, 0))

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------
    def open_save_file(self) -> None:
        initdir = os.getcwd()
        for env_var in ("ProgramFiles(x86)", "ProgramFiles"):
            base_path = os.environ.get(env_var)
            if not base_path:
                continue
            candidate = os.path.join(base_path, "Steam", "userdata")
            if os.path.exists(candidate):
                initdir = candidate
                break

        filename = filedialog.askopenfilename(
            title="아이작 세이브파일 선택",
            initialdir=initdir,
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return

        try:
            with open(filename, "rb") as file:
                self.data = file.read()
        except OSError as exc:
            messagebox.showerror("파일 오류", f"세이브 파일을 열 수 없습니다.\n{exc}")
            return

        self.filename = filename
        basename = os.path.basename(filename)
        self.loaded_file_var.set(f"불러온 파일 (Loaded File): {basename}")
        self.refresh_current_values()

    # ------------------------------------------------------------------
    # Numeric field helpers
    # ------------------------------------------------------------------
    def apply_field(self, key: str, preset: int | None = None) -> bool:
        if key not in self._numeric_config:
            return False

        if self.data is None or not self.filename:
            messagebox.showwarning("파일 없음", "먼저 세이브 파일을 열어주세요.")
            return False

        vars_map = self._numeric_vars[key]
        entry_var = vars_map["entry"]
        config = self._numeric_config[key]

        raw_value = preset if preset is not None else entry_var.get()
        try:
            new_value = int(raw_value)
        except (TypeError, ValueError):
            messagebox.showerror(
                "유효하지 않은 값",
                f"{config['description']}에 사용할 정수를 입력해주세요.",
            )
            return False

        try:
            section_offsets = script.getSectionOffsets(self.data)
            base_offset = section_offsets[1] + 0x4 + int(config["offset"])
            updated = script.alterInt(self.data, base_offset, new_value)
            updated_with_checksum = script.updateChecksum(updated)
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            messagebox.showerror(
                "업데이트 실패",
                f"{config['description']} 값을 수정하지 못했습니다.\n{exc}",
            )
            return False

        self.data = updated_with_checksum
        try:
            with open(self.filename, "wb") as file:
                file.write(self.data)
        except OSError as exc:
            messagebox.showerror("저장 실패", f"세이브 파일을 저장하지 못했습니다.\n{exc}")
            return False

        self.refresh_current_values()
        return True

    def set_donation_and_greed_to_max(self) -> None:
        if self.data is None or not self.filename:
            messagebox.showwarning("파일 없음", "먼저 세이브 파일을 열어주세요.")
            return
        if self.apply_field("donation", preset=999):
            self.apply_field("greed", preset=999)

    def refresh_current_values(self) -> None:
        if self.data is None:
            for key in self._numeric_order:
                vars_map = self._numeric_vars[key]
                vars_map["current"].set("0")
                vars_map["entry"].set("0")
            return

        try:
            section_offsets = script.getSectionOffsets(self.data)
            base_offset = section_offsets[1] + 0x4
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            messagebox.showerror("읽기 실패", f"값을 불러오지 못했습니다.\n{exc}")
            return

        for key in self._numeric_order:
            config = self._numeric_config[key]
            vars_map = self._numeric_vars[key]
            try:
                value = script.getInt(self.data, base_offset + int(config["offset"]))
            except Exception:
                value = 0
            value_str = str(value)
            vars_map["current"].set(value_str)
            vars_map["entry"].set(value_str)


def main() -> None:
    app = IsaacSaveEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
