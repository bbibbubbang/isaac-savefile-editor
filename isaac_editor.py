"""New Tkinter-based interface for The Binding of Isaac save editor.

This module provides a refreshed GUI with tab structure and a main tab that
allows users to edit key numeric values such as donation machine totals and
win streaks. It replaces the legacy ``gui.py`` entry point for everyday use
while keeping existing backend logic in ``script.py``.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
from typing import Callable, Dict, List, Optional, Set

from ttkwidgets import CheckboxTreeview

import script


DATA_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = DATA_DIR / "settings.json"
DEFAULT_SETTINGS: Dict[str, object] = {
    "remember_path": False,
    "last_path": "",
    "auto_set_999": False,
    "auto_overwrite": False,
    "source_save_path": "",
    "target_save_path": "",
}

COMPLETION_UNLOCK_VALUE = 15
TOTAL_COMPLETION_MARKS = 12


class TreeManager:
    """Manage sorting and column updates for :class:`CheckboxTreeview`."""

    def __init__(self, tree: CheckboxTreeview, records: Dict[str, Dict[str, object]]):
        self.tree = tree
        self.records = records
        self._next_direction: Dict[str, bool] = {}
        self._last_sort_column: Optional[str] = None
        self._last_sort_ascending: bool = True

    def sort(self, column: str, ascending: Optional[bool] = None, update_toggle: bool = True) -> None:
        if not self.records:
            return
        if ascending is None:
            ascending = self._next_direction.get(column, True)
        entries = list(self.records.values())
        if column == "name":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            if not ascending:
                entries.reverse()
        elif column == "unlock":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            entries.sort(key=lambda info: 1 if info.get("unlock") else 0, reverse=not ascending)
        elif column == "quality":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            entries.sort(
                key=lambda info: info.get("quality") if info.get("quality") is not None else -1,
                reverse=not ascending,
            )
        for index, info in enumerate(entries):
            self.tree.move(str(info["iid"]), "", index)
        if update_toggle:
            self._next_direction[column] = not ascending
        else:
            self._next_direction.setdefault(column, not ascending)
        self._last_sort_column = column
        self._last_sort_ascending = ascending

    def resort(self) -> None:
        if self._last_sort_column:
            self.sort(self._last_sort_column, ascending=self._last_sort_ascending, update_toggle=False)

    def set_unlock(self, iid: str, unlocked: bool) -> None:
        if iid in self.records:
            self.records[iid]["unlock"] = bool(unlocked)
            self.tree.set(iid, "unlock", "O" if unlocked else "X")


class IsaacSaveEditor(tk.Tk):
    """Main application window for the save editor."""

    SECRET_TAB_LABELS: Dict[str, str] = {
        "Character": "캐릭터",
        "Map": "맵",
        "Boss": "보스",
        "Item": "업적아이템",
        "Item.Passive": "패시브",
        "Item.Active": "액티브",
        "Other": "기타",
        "None": "무효과",
        "Trinket": "장신구",
        "Pickup": "픽업",
        "Card": "카드",
        "Rune": "룬",
        "Pill": "알약",
    }
    SECRET_FALLBACK_TYPE = "Other"

    def __init__(self) -> None:
        super().__init__()
        self.title("Isaac Savefile Editor")

        self.filename: str = ""
        self.data: bytes | None = None

        self.settings_path = SETTINGS_PATH
        self.settings = self._load_settings()
        self._auto_set_999_default = bool(self.settings.get("auto_set_999", False))
        self._auto_overwrite_default = bool(self.settings.get("auto_overwrite", False))
        self.source_save_path = self._normalize_save_path(self.settings.get("source_save_path"))
        self.target_save_path = self._normalize_save_path(self.settings.get("target_save_path"))
        self.settings["source_save_path"] = self.source_save_path
        self.settings["target_save_path"] = self.target_save_path
        remember_path = bool(self.settings.get("remember_path", False))
        self.remember_path_var = tk.BooleanVar(value=remember_path)
        self._default_loaded_text = "불러온 파일 (Loaded File): 없음"

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

        self._locked_tree_ids: Set[int] = set()

        (
            self._completion_characters,
            self._completion_marks_by_character,
        ) = self._load_completion_records()
        self._completion_character_var = tk.StringVar()
        self._completion_display_to_index: Dict[str, int] = {}
        self._completion_tree: Optional[CheckboxTreeview] = None
        self._completion_current_mark_ids: List[str] = []
        self._current_completion_char_index: Optional[int] = None

        (
            self._item_records,
            self._item_ids_by_type,
            self._item_lookup_by_name,
        ) = self._load_item_records()

        (
            self._secret_records_by_type,
            self._secret_ids_by_type,
            self._secret_tab_labels,
            self._secret_tab_order,
            self._secret_details_by_id,
        ) = self._load_secret_records(self._item_lookup_by_name)
        self._secret_trees: Dict[str, CheckboxTreeview] = {}
        self._secret_managers: Dict[str, TreeManager] = {}

        self._item_trees: Dict[str, CheckboxTreeview] = {}
        self._item_managers: Dict[str, TreeManager] = {}

        self._secret_to_challenges: Dict[str, Set[str]] = {}
        self._challenge_to_secrets: Dict[str, Set[str]] = {}
        self._challenge_records = self._load_challenge_records()
        self._challenge_tree: Optional[CheckboxTreeview] = None
        self._challenge_manager: Optional[TreeManager] = None
        self._challenge_ids: List[str] = [record["iid"] for record in self._challenge_records]

        self._build_secret_challenge_links()

        self._build_layout()
        self.refresh_current_values()
        self.after(0, self._perform_startup_tasks)

    @staticmethod
    def _build_lookup_keys(*values: str) -> Set[str]:
        keys: Set[str] = set()
        articles = ("the ", "a ", "an ")
        for value in values:
            if not value:
                continue
            normalized = " ".join(value.replace("’", "'").split()).casefold()
            if not normalized:
                continue
            candidates = {normalized, normalized.replace("'", "")}
            stripped = normalized.strip("!?.")
            if stripped:
                candidates.add(stripped)
            no_punct = re.sub(r"[!?.]", "", normalized).strip()
            if no_punct:
                candidates.add(no_punct)
            no_paren = re.sub(r"\s*\(.*?\)", "", normalized).strip()
            if no_paren:
                candidates.add(no_paren)
            for candidate in list(candidates):
                if not candidate:
                    continue
                for prefix in articles:
                    if candidate.startswith(prefix):
                        stripped_candidate = candidate[len(prefix) :]
                        if stripped_candidate:
                            candidates.add(stripped_candidate)
            keys.update(candidate for candidate in candidates if candidate)
        return keys

    @staticmethod
    def _normalize_save_path(value: object) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return os.path.abspath(normalized)
        return ""

    @staticmethod
    def _path_contains_steam(path: str) -> bool:
        normalized = path.replace("\\", "/").casefold()
        return "steam" in normalized

    @staticmethod
    def _format_selected_path(path: str) -> str:
        if not path:
            return "선택된 파일: 없음"
        return f"선택된 파일: {os.path.normpath(path)}"
    # ------------------------------------------------------------------
    # Layout construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.notebook = notebook

        main_tab = ttk.Frame(notebook, padding=12)
        main_tab.columnconfigure(0, weight=1)
        notebook.add(main_tab, text="메인")
        self._build_main_tab(main_tab)

        completion_tab = ttk.Frame(notebook, padding=12)
        completion_tab.columnconfigure(0, weight=1)
        completion_tab.rowconfigure(2, weight=1)
        self._build_completion_tab(completion_tab)

        def add_secret_tab(secret_type: str) -> None:
            tab_label = self._secret_tab_labels.get(secret_type, secret_type)
            secrets_tab = ttk.Frame(notebook, padding=12)
            secrets_tab.columnconfigure(0, weight=1)
            notebook.add(secrets_tab, text=tab_label)
            self._build_secrets_tab(secrets_tab, secret_type)

        secret_order = [
            secret_type
            for secret_type in self._secret_tab_order
            if self._secret_ids_by_type.get(secret_type)
        ]
        boss_tab_type: Optional[str] = None
        for secret_type in secret_order:
            if secret_type == "Boss" and boss_tab_type is None:
                boss_tab_type = secret_type
                continue
            add_secret_tab(secret_type)
        if boss_tab_type:
            add_secret_tab(boss_tab_type)

        notebook.add(completion_tab, text="체크리스트")

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

        self.loaded_file_var = tk.StringVar(value=self._default_loaded_text)
        loaded_file_label = ttk.Label(top_frame, textvariable=self.loaded_file_var)
        loaded_file_label.grid(column=1, row=0, sticky="w", padx=(10, 0))

        remember_check = ttk.Checkbutton(
            top_frame,
            text="세이브파일 경로 기억",
            variable=self.remember_path_var,
            command=self._on_remember_path_toggle,
        )
        remember_check.grid(column=0, row=1, columnspan=2, sticky="w", pady=(8, 0))

        self.auto_set_999_var = tk.BooleanVar(value=self._auto_set_999_default)
        self.auto_overwrite_var = tk.BooleanVar(value=self._auto_overwrite_default)
        self.source_save_display_var = tk.StringVar(
            value=self._format_selected_path(self.source_save_path)
        )
        self.target_save_display_var = tk.StringVar(
            value=self._format_selected_path(self.target_save_path)
        )

        overwrite_frame = ttk.LabelFrame(
            container,
            text="세이브파일 덮어쓰기",
            padding=(12, 10),
        )
        overwrite_frame.grid(column=0, row=1, sticky="ew", pady=(15, 0))
        overwrite_frame.columnconfigure(1, weight=1)

        auto_overwrite_check = ttk.Checkbutton(
            overwrite_frame,
            text="세이브파일 자동 덮어쓰기",
            variable=self.auto_overwrite_var,
            command=self._on_auto_overwrite_toggle,
        )
        auto_overwrite_check.grid(column=0, row=0, sticky="w")

        help_button = ttk.Button(
            overwrite_frame,
            text="도움말",
            command=self._show_auto_overwrite_help,
        )
        help_button.grid(column=1, row=0, sticky="e")

        source_button = ttk.Button(
            overwrite_frame,
            text="원본 세이브파일 열기",
            command=self._select_source_save_file,
        )
        source_button.grid(column=0, row=1, sticky="w", pady=(8, 0))

        source_label = ttk.Label(
            overwrite_frame,
            textvariable=self.source_save_display_var,
            wraplength=420,
            justify="left",
        )
        source_label.grid(column=1, row=1, sticky="w", padx=(10, 0), pady=(8, 0))

        target_button = ttk.Button(
            overwrite_frame,
            text="덮어쓰기할 세이브파일 열기",
            command=self._select_target_save_file,
        )
        target_button.grid(column=0, row=2, sticky="w", pady=(8, 0))

        target_label = ttk.Label(
            overwrite_frame,
            textvariable=self.target_save_display_var,
            wraplength=420,
            justify="left",
        )
        target_label.grid(column=1, row=2, sticky="w", padx=(10, 0), pady=(8, 0))

        numeric_start_row = 2
        for index, key in enumerate(self._numeric_order):
            row_index = numeric_start_row + index
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
                command=lambda field_key=key: self.apply_field(field_key, preserve_entry=True),
                is_first=index == 0,
            )

        auto_999_row = numeric_start_row + len(self._numeric_order)
        auto_999_frame = ttk.Frame(container)
        auto_999_frame.grid(column=0, row=auto_999_row, sticky="ew", pady=(12, 0))
        auto_999_frame.columnconfigure(0, weight=1)

        auto_999_check = ttk.Checkbutton(
            auto_999_frame,
            text="프로그램 시작 시 999로 설정",
            variable=self.auto_set_999_var,
            command=self._on_auto_set_999_toggle,
        )
        auto_999_check.grid(column=0, row=0, sticky="w")

        set_999_button = ttk.Button(
            auto_999_frame,
            text="기부/그리드 기계/에덴 토큰 999로 설정",
            command=self.set_donation_greed_eden_to_max,
        )
        set_999_button.grid(column=1, row=0, sticky="e", padx=(10, 0))

        self._update_source_display()
        self._update_target_display()

    def _update_source_display(self) -> None:
        if hasattr(self, "source_save_display_var"):
            self.source_save_display_var.set(
                self._format_selected_path(self.source_save_path)
            )

    def _update_target_display(self) -> None:
        if hasattr(self, "target_save_display_var"):
            self.target_save_display_var.set(
                self._format_selected_path(self.target_save_path)
            )

    def _build_completion_tab(self, container: ttk.Frame) -> None:
        container.columnconfigure(0, weight=1)

        header = ttk.Frame(container)
        header.grid(column=0, row=0, sticky="w")

        ttk.Label(header, text="캐릭터: ").pack(side="left")

        self._completion_display_to_index.clear()
        character_options: List[str] = []
        for info in self._completion_characters:
            display = self._format_completion_character_display(info)
            self._completion_display_to_index[display] = int(info["index"])
            character_options.append(display)

        character_box = ttk.Combobox(
            header,
            textvariable=self._completion_character_var,
            state="readonly",
            values=character_options,
            width=26,
        )
        character_box.pack(side="left", padx=(6, 0))
        character_box.bind("<<ComboboxSelected>>", self._on_completion_character_selected)

        ttk.Label(
            container,
            text="체크박스를 클릭하면 즉시 저장됩니다.",
        ).grid(column=0, row=1, sticky="w", pady=(10, 0))

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=2, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_completion_tree(tree_container)
        tree.column("#0", anchor="w", width=420, stretch=True)
        tree.bind("<ButtonRelease-1>", self._on_completion_tree_click, True)
        self._completion_tree = tree

        unlock_all_button = ttk.Button(
            container,
            text="모든 캐릭터 체크리스트 완료",
            command=self._unlock_all_completion_marks_all_characters,
        )
        unlock_all_button.grid(column=0, row=3, sticky="e", pady=(12, 0))

        if character_options:
            character_box.current(0)
            self._on_completion_character_selected()
        else:
            character_box.configure(state="disabled")
            if self._completion_tree is not None:
                self._completion_tree.state(("disabled",))

    @staticmethod
    def _format_completion_character_display(info: Dict[str, object]) -> str:
        english = str(info.get("english", "")).strip()
        korean = str(info.get("korean", "")).strip()
        if korean and english and korean != english:
            return f"{korean} ({english})"
        if korean:
            return korean
        if english:
            return english
        return f"Character {info.get('index', '')}"

    def _on_completion_character_selected(self, event: object | None = None) -> None:
        selected = self._completion_character_var.get()
        char_index = self._completion_display_to_index.get(selected)
        if char_index is None:
            return
        self._populate_completion_tree_for_character(char_index)

    def _populate_completion_tree_for_character(self, char_index: int) -> None:
        tree = self._completion_tree
        if tree is None:
            self._current_completion_char_index = char_index
            return
        marks = self._completion_marks_by_character.get(char_index, [])
        try:
            marks_sorted = sorted(marks, key=lambda info: int(info.get("mark_index", 0)))
        except TypeError:
            marks_sorted = marks
        self._lock_tree(tree)
        try:
            tree.delete(*tree.get_children())
            mark_ids: List[str] = []
            for mark in marks_sorted:
                mark_id = str(mark.get("mark_index", ""))
                if not mark_id:
                    continue
                display = str(mark.get("display") or mark.get("mark_name") or mark_id)
                if tree.exists(mark_id):
                    tree.delete(mark_id)
                tree.insert("", "end", iid=mark_id, text=display)
                mark_ids.append(mark_id)
            self._completion_current_mark_ids = mark_ids
        finally:
            self._unlock_tree(tree)
        self._current_completion_char_index = char_index
        self._refresh_completion_tab()

    def _build_secrets_tab(self, container: ttk.Frame, secret_type: str) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")
        ttk.Button(
            button_frame,
            text="모두 선택 (Select All)",
            command=lambda t=secret_type: self._select_all_secrets(t),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_frame,
            text="모두 해제 (Select None)",
            command=lambda t=secret_type: self._select_none_secrets(t),
        ).pack(side="left")
        ttk.Button(
            button_frame,
            text="선택 해금",
            command=lambda t=secret_type: self._unlock_selected_secrets(t),
        ).pack(side="left", padx=(12, 6))
        ttk.Button(
            button_frame,
            text="선택 미해금",
            command=lambda t=secret_type: self._lock_selected_secrets(t),
        ).pack(side="left")

        include_quality = secret_type.startswith("Item.")
        info_text = None
        if include_quality:
            info_text = "업적 아이템은 모두 해금하고, 패시브/액티브 탭에서 해금 여부를 변경하세요."

        tree_row = 1
        if info_text:
            ttk.Label(
                container,
                text=info_text,
                wraplength=520,
                justify="left",
            ).grid(column=0, row=1, sticky="w", pady=(8, 0))
            tree_row = 2

        container.rowconfigure(tree_row, weight=1)

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=tree_row, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        columns: tuple[str, ...]
        if include_quality:
            columns = ("unlock", "quality")
        else:
            columns = ("unlock",)
        tree = self._create_tree(tree_container, columns)
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)
        if include_quality:
            tree.column("quality", anchor="center", width=120, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", text="이름 (Name)", command=lambda m=manager: m.sort("name"))
        tree.heading("unlock", text="해금 여부 (Unlock)", command=lambda m=manager: m.sort("unlock"))
        if include_quality:
            tree.heading("quality", text="등급 (Quality)", command=lambda m=manager: m.sort("quality"))

        records: Dict[str, Dict[str, object]] = {}
        for record in self._secret_records_by_type.get(secret_type, []):
            quality_value = record.get("quality")
            values: List[str] = ["X"]
            if include_quality:
                quality_display = "-" if quality_value is None else str(quality_value)
                values.append(quality_display)
            tree.insert("", "end", iid=record["iid"], text=record["display"], values=tuple(values))
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record["name_sort"],
                "unlock": False,
                "quality": quality_value if include_quality else None,
            }
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._secret_trees[secret_type] = tree
        self._secret_managers[secret_type] = manager

    def _build_item_tab(self, container: ttk.Frame, item_type: str) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")
        ttk.Button(
            button_frame,
            text="모두 선택 (Select All)",
            command=lambda t=item_type: self._select_all_items(t),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_frame,
            text="모두 해제 (Select None)",
            command=lambda t=item_type: self._select_none_items(t),
        ).pack(side="left")
        ttk.Button(
            button_frame,
            text="선택 해금",
            command=lambda t=item_type: self._unlock_selected_items(t),
        ).pack(side="left", padx=(12, 6))
        ttk.Button(
            button_frame,
            text="선택 미해금",
            command=lambda t=item_type: self._lock_selected_items(t),
        ).pack(side="left")

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=1, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_tree(tree_container, ("unlock", "quality"))
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)
        tree.column("quality", anchor="center", width=120, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", text="이름 (Name)", command=lambda m=manager: m.sort("name"))
        tree.heading("unlock", text="해금 여부 (Unlock)", command=lambda m=manager: m.sort("unlock"))
        tree.heading("quality", text="등급 (Quality)", command=lambda m=manager: m.sort("quality"))

        records: Dict[str, Dict[str, object]] = {}
        for item_id, record in self._item_records.get(item_type, {}).items():
            quality = record.get("quality")
            quality_display = "-" if quality is None else str(quality)
            tree.insert("", "end", iid=item_id, text=record["display"], values=("X", quality_display))
            records[item_id] = {
                "iid": item_id,
                "name_sort": record["name_sort"],
                "unlock": False,
                "quality": quality,
            }
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._item_trees[item_type] = tree
        self._item_managers[item_type] = manager

    def _build_challenges_tab(self, container: ttk.Frame) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")
        ttk.Button(
            button_frame,
            text="모두 선택 (Select All)",
            command=self._select_all_challenges,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_frame,
            text="모두 해제 (Select None)",
            command=self._select_none_challenges,
        ).pack(side="left")
        ttk.Button(
            button_frame,
            text="선택 해금",
            command=self._unlock_selected_challenges,
        ).pack(side="left", padx=(12, 6))
        ttk.Button(
            button_frame,
            text="선택 미해금",
            command=self._lock_selected_challenges,
        ).pack(side="left")

        ttk.Label(
            container,
            text="도전과제는 모두 해금하고, 다른 아이템 탭에서 해금여부를 변경하세요.",
            wraplength=520,
            justify="left",
        ).grid(column=0, row=1, sticky="w", pady=(8, 0))

        tree_row = 2
        container.rowconfigure(tree_row, weight=1)

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=tree_row, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_tree(tree_container, ("unlock",))
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", text="이름 (Name)", command=lambda m=manager: m.sort("name"))
        tree.heading("unlock", text="해금 여부 (Unlock)", command=lambda m=manager: m.sort("unlock"))

        records: Dict[str, Dict[str, object]] = {}
        for record in self._challenge_records:
            tree.insert("", "end", iid=record["iid"], text=record["display"], values=("X",))
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record["name_sort"],
                "unlock": False,
                "quality": None,
            }
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._challenge_tree = tree
        self._challenge_manager = manager

    def _create_completion_tree(self, container: ttk.Frame) -> CheckboxTreeview:
        tree = CheckboxTreeview(container, columns=(), show="tree", selectmode="none")
        tree.grid(column=0, row=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        yscroll.grid(column=1, row=0, sticky="ns")
        tree.configure(yscrollcommand=yscroll.set)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        xscroll.grid(column=0, row=1, sticky="ew")
        tree.configure(xscrollcommand=xscroll.set)
        return tree

    def _create_tree(self, container: ttk.Frame, columns: tuple[str, ...]) -> CheckboxTreeview:
        tree = CheckboxTreeview(container, columns=columns, show="tree headings", selectmode="none")
        tree.grid(column=0, row=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        yscroll.grid(column=1, row=0, sticky="ns")
        tree.configure(yscrollcommand=yscroll.set)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        xscroll.grid(column=0, row=1, sticky="ew")
        tree.configure(xscrollcommand=xscroll.set)
        return tree

    def _lock_tree(self, tree: CheckboxTreeview) -> None:
        self._locked_tree_ids.add(id(tree))

    def _unlock_tree(self, tree: CheckboxTreeview) -> None:
        self._locked_tree_ids.discard(id(tree))

    def _is_tree_locked(self, tree: CheckboxTreeview) -> bool:
        return id(tree) in self._locked_tree_ids

    def _get_checked_or_warn(self, tree: CheckboxTreeview) -> Set[str] | None:
        selected = set(tree.get_checked())
        if not selected:
            messagebox.showinfo("선택 없음", "먼저 체크박스에서 항목을 선택해주세요.")
            return None
        return selected
    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_completion_records(
        self,
    ) -> tuple[List[Dict[str, object]], Dict[int, List[Dict[str, object]]]]:
        characters_by_index: Dict[int, Dict[str, object]] = {
            index: {"index": index, "english": name, "korean": name}
            for index, name in enumerate(getattr(script, "characters", []))
        }
        default_marks_template = [
            {"mark_index": idx, "mark_name": mark_name, "display": mark_name}
            for idx, mark_name in enumerate(getattr(script, "checklist_order", []))
        ]
        marks_by_character: Dict[int, List[Dict[str, object]]] = {
            index: [entry.copy() for entry in default_marks_template]
            for index in characters_by_index
        }

        csv_path = DATA_DIR / "ui_completion_marks.csv"
        if csv_path.exists():
            try:
                with csv_path.open(encoding="utf-8-sig", newline="") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        try:
                            char_index = int((row.get("CharacterIndex") or "").strip())
                            mark_index = int((row.get("MarkIndex") or "").strip())
                        except (TypeError, ValueError):
                            continue
                        english_name = (row.get("CharacterName") or "").strip()
                        korean_name = (row.get("Korean") or "").strip()
                        mark_name = (row.get("MarkName") or "").strip()
                        character_info = characters_by_index.setdefault(
                            char_index,
                            {
                                "index": char_index,
                                "english": english_name or f"Character {char_index}",
                                "korean": korean_name or english_name or f"Character {char_index}",
                            },
                        )
                        if english_name:
                            character_info["english"] = english_name
                        if korean_name:
                            character_info["korean"] = korean_name
                        marks = marks_by_character.setdefault(
                            char_index,
                            [entry.copy() for entry in default_marks_template],
                        )
                        mark_record = {
                            "mark_index": mark_index,
                            "mark_name": mark_name or f"Mark {mark_index}",
                            "display": mark_name or f"Mark {mark_index}",
                        }
                        replaced = False
                        for existing in marks:
                            if int(existing.get("mark_index", -1)) == mark_index:
                                existing.update(mark_record)
                                replaced = True
                                break
                        if not replaced:
                            marks.append(mark_record)
            except OSError:
                pass

        sorted_indices = sorted(characters_by_index)
        characters = []
        normalized_marks: Dict[int, List[Dict[str, object]]] = {}
        for index in sorted_indices:
            info = characters_by_index[index]
            info.setdefault("english", f"Character {index}")
            info.setdefault("korean", info["english"])
            info["index"] = index
            characters.append(info)
            marks = marks_by_character.get(index, [entry.copy() for entry in default_marks_template])
            try:
                marks.sort(key=lambda entry: int(entry.get("mark_index", 0)))
            except TypeError:
                pass
            for entry in marks:
                entry.setdefault("mark_name", f"Mark {entry.get('mark_index', 0)}")
                entry.setdefault("display", entry["mark_name"])
            normalized_marks[index] = marks

        if not characters:
            # fallback when script data and CSV are missing
            characters = [
                {
                    "index": idx,
                    "english": name,
                    "korean": name,
                }
                for idx, name in enumerate(
                    [
                        "Isaac",
                        "Maggy",
                        "Cain",
                        "Judas",
                        "???",
                        "Eve",
                        "Samson",
                        "Azazel",
                        "Lazarus",
                        "Eden",
                        "The Lost",
                        "Lilith",
                        "Keeper",
                        "Apollyon",
                        "Forgotten",
                        "Bethany",
                        "Jacob & Esau",
                        "T Isaac",
                        "T Maggy",
                        "T Cain",
                        "T Judas",
                        "T ???",
                        "T Eve",
                        "T Samson",
                        "T Azazel",
                        "T Lazarus",
                        "T Eden",
                        "T Lost",
                        "T Lilith",
                        "T Keeper",
                        "T Apollyon",
                        "T Forgotten",
                        "T Bethany",
                        "T Jacob",
                    ]
                )
            ]
            normalized_marks = {
                info["index"]: [entry.copy() for entry in default_marks_template]
                for info in characters
            }

        return characters, normalized_marks

    def _load_secret_records(
        self,
        item_lookup: Optional[Dict[str, Dict[str, object]]] = None,
    ) -> tuple[
        Dict[str, List[Dict[str, object]]],
        Dict[str, List[str]],
        Dict[str, str],
        List[str],
        Dict[str, Dict[str, object]],
    ]:
        csv_path = DATA_DIR / "ui_secrets.csv"
        records_by_type: Dict[str, List[Dict[str, object]]] = {}
        ids_by_type: Dict[str, List[str]] = {}
        tab_labels: Dict[str, str] = {}
        type_order: List[str] = []
        details_by_id: Dict[str, Dict[str, object]] = {}
        allowed_types = {
            "Character",
            "Map",
            "Boss",
            "Item",
            "Other",
            "None",
            "Trinket",
            "Pickup",
            "Card",
            "Rune",
            "Pill",
        }
        item_lookup = item_lookup or {}
        if not csv_path.exists():
            return records_by_type, ids_by_type, tab_labels, type_order, details_by_id

        def register_type(secret_type: str) -> None:
            if secret_type not in records_by_type:
                records_by_type[secret_type] = []
                ids_by_type[secret_type] = []
                tab_labels[secret_type] = self.SECRET_TAB_LABELS.get(secret_type, secret_type)
                type_order.append(secret_type)
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                secret_id = (row.get("SecretID") or "").strip()
                if not secret_id:
                    continue
                secret_type_raw = (row.get("Type") or "").strip()
                if not secret_type_raw:
                    secret_type_raw = self.SECRET_FALLBACK_TYPE
                if secret_type_raw not in allowed_types:
                    secret_type_raw = self.SECRET_FALLBACK_TYPE
                korean = (row.get("Korean") or "").strip()
                unlock_name = (row.get("UnlockName") or "").strip()
                secret_name = (row.get("SecretName") or "").strip()
                quality_value: Optional[int] = None
                lookup_names = (unlock_name, secret_name, korean)
                if secret_type_raw == "Item":
                    matched_info: Optional[Dict[str, object]] = None
                    for key in self._build_lookup_keys(*lookup_names):
                        matched_info = item_lookup.get(key)
                        if matched_info:
                            break
                    if matched_info:
                        item_type = str(matched_info.get("item_type"))
                        if item_type in {"Passive", "Active"}:
                            secret_type = f"Item.{item_type}"
                            try:
                                quality_value = (
                                    int(matched_info.get("quality"))
                                    if matched_info.get("quality") is not None
                                    else None
                                )
                            except (TypeError, ValueError):
                                quality_value = None
                        else:
                            secret_type = self.SECRET_FALLBACK_TYPE
                    else:
                        secret_type = self.SECRET_FALLBACK_TYPE
                else:
                    secret_type = secret_type_raw
                register_type(secret_type)
                primary = korean or unlock_name or secret_name or secret_id
                secondary = secret_name or unlock_name
                if secondary and primary != secondary:
                    display = f"{primary} ({secondary})"
                else:
                    display = primary
                record = {
                    "iid": secret_id,
                    "display": display,
                    "name_sort": display.lower(),
                    "quality": quality_value,
                    "unlock_name": unlock_name,
                    "secret_name": secret_name,
                    "korean": korean,
                }
                records_by_type[secret_type].append(record)
                ids_by_type[secret_type].append(secret_id)
                details_by_id[secret_id] = {
                    "unlock_name": unlock_name,
                    "secret_name": secret_name,
                    "korean": korean,
                    "display": display,
                    "secret_type": secret_type,
                }
        return records_by_type, ids_by_type, tab_labels, type_order, details_by_id

    def _load_item_records(
        self,
    ) -> tuple[
        Dict[str, Dict[str, Dict[str, object]]],
        Dict[str, List[str]],
        Dict[str, Dict[str, object]],
    ]:
        csv_path = DATA_DIR / "ui_items.csv"
        records: Dict[str, Dict[str, Dict[str, object]]] = {"Passive": {}, "Active": {}}
        ids_by_type: Dict[str, List[str]] = {"Passive": [], "Active": []}
        lookup_by_name: Dict[str, Dict[str, object]] = {}
        if not csv_path.exists():
            return records, ids_by_type, lookup_by_name
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                item_id = (row.get("ItemID") or "").strip()
                item_type = (row.get("Type") or "").strip()
                if not item_id or item_type not in records:
                    continue
                korean = (row.get("Korean") or "").strip()
                english = (row.get("ItemName") or "").strip()
                quality_text = (row.get("Quality") or "").strip()
                try:
                    quality_value = int(quality_text) if quality_text else None
                except ValueError:
                    quality_value = None
                primary = korean or english or item_id
                if english and primary != english:
                    display = f"{primary} ({english})"
                else:
                    display = primary
                record = {
                    "iid": item_id,
                    "display": display,
                    "name_sort": display.lower(),
                    "quality": quality_value,
                    "english": english,
                    "korean": korean,
                    "item_type": item_type,
                }
                records[item_type][item_id] = record
                ids_by_type[item_type].append(item_id)
                for key in self._build_lookup_keys(english, korean):
                    lookup_by_name.setdefault(key, record)
        return records, ids_by_type, lookup_by_name

    def _load_challenge_records(self) -> List[Dict[str, str]]:
        csv_path = DATA_DIR / "ui_challenges.csv"
        records: List[Dict[str, str]] = []
        if not csv_path.exists():
            return records
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                challenge_id = (row.get("ChallengeID") or "").strip()
                if not challenge_id:
                    continue
                korean = (row.get("Korean") or "").strip()
                challenge_name = (row.get("ChallengeName") or "").strip()
                primary = korean or challenge_name or challenge_id
                if challenge_name and primary != challenge_name:
                    display = f"{primary} ({challenge_name})"
                else:
                    display = primary
                records.append(
                    {
                        "iid": challenge_id,
                        "display": display,
                        "name_sort": display.lower(),
                        "english": challenge_name,
                        "korean": korean,
                    }
                )
        return records

    def _build_secret_challenge_links(self) -> None:
        details = getattr(self, "_secret_details_by_id", {}) or {}
        if not details or not self._challenge_records:
            self._secret_to_challenges = {}
            self._challenge_to_secrets = {}
            return

        name_to_challenges: Dict[str, Set[str]] = {}
        for record in self._challenge_records:
            challenge_id = str(record.get("iid", "")).strip()
            if not challenge_id:
                continue
            english = str(record.get("english", "")).strip()
            korean = str(record.get("korean", "")).strip()
            for key in self._build_lookup_keys(english, korean):
                if key:
                    name_to_challenges.setdefault(key, set()).add(challenge_id)

        secret_to_challenges: Dict[str, Set[str]] = {}
        challenge_to_secrets: Dict[str, Set[str]] = {}
        for secret_id, info in details.items():
            unlock_name = str(info.get("unlock_name", "")).strip()
            secret_name = str(info.get("secret_name", "")).strip()
            korean = str(info.get("korean", "")).strip()
            matched: Set[str] = set()
            for key in self._build_lookup_keys(unlock_name, secret_name, korean):
                matched.update(name_to_challenges.get(key, set()))
            if not matched:
                continue
            secret_to_challenges[secret_id] = matched
            for challenge_id in matched:
                challenge_to_secrets.setdefault(challenge_id, set()).add(secret_id)

        self._secret_to_challenges = secret_to_challenges
        self._challenge_to_secrets = challenge_to_secrets
    # ------------------------------------------------------------------
    # Event handlers and select helpers
    # ------------------------------------------------------------------
    def _on_completion_tree_click(self, event: tk.Event) -> None:
        tree = self._completion_tree
        if tree is None or event.widget is not tree:
            return
        if self._is_tree_locked(tree):
            return
        if self._current_completion_char_index is None:
            return
        element = tree.identify("element", event.x, event.y)
        if "image" not in element:
            return
        self.after_idle(self._commit_completion_tree_state)

    def _commit_completion_tree_state(self) -> None:
        tree = self._completion_tree
        if tree is None:
            return
        if self._is_tree_locked(tree):
            return
        if self._current_completion_char_index is None:
            return
        if not self._completion_current_mark_ids:
            return
        new_values: List[int] = []
        for mark_id in self._completion_current_mark_ids:
            checked = tree.tag_has("checked", mark_id)
            new_values.append(COMPLETION_UNLOCK_VALUE if checked else 0)
        success = self._apply_update(
            lambda data, idx=self._current_completion_char_index, values=new_values: script.updateCheckListUnlocks(
                data, idx, values
            ),
            "체크리스트를 업데이트하지 못했습니다.",
        )
        if not success:
            self._refresh_completion_tab()

    def _unlock_all_completion_marks_all_characters(self) -> None:
        if not self._ensure_data_loaded():
            return
        proceed = messagebox.askyesno(
            "체크리스트 완료",
            "모든 캐릭터의 체크리스트를 완료하시겠습니까?",
            icon="question",
        )
        if not proceed:
            return
        script_character_count = len(getattr(script, "characters", []))
        indices_from_script = set(range(script_character_count))
        indices_from_ui = {int(info.get("index", idx)) for idx, info in enumerate(self._completion_characters)}
        indices_from_marks = {int(index) for index in self._completion_marks_by_character}
        char_indices = sorted(indices_from_script | indices_from_ui | indices_from_marks)
        if not char_indices:
            messagebox.showwarning("체크리스트 완료", "완료할 캐릭터 정보를 찾을 수 없습니다.")
            return
        mark_count = max(
            (len(marks) for marks in self._completion_marks_by_character.values()),
            default=TOTAL_COMPLETION_MARKS,
        )
        if mark_count <= 0:
            mark_count = TOTAL_COMPLETION_MARKS

        def updater(data: bytes) -> bytes:
            result = data
            payload = [COMPLETION_UNLOCK_VALUE] * mark_count
            for index in char_indices:
                result = script.updateCheckListUnlocks(result, index, payload)
            return result

        if self._apply_update(updater, "모든 캐릭터 체크리스트를 완료하지 못했습니다."):
            messagebox.showinfo("완료", "모든 캐릭터 체크리스트를 완료했습니다.")

    def _select_all_secrets(self, secret_type: str) -> None:
        tree = self._secret_trees.get(secret_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            for secret_id in self._secret_ids_by_type.get(secret_type, []):
                tree.change_state(secret_id, "checked")
        finally:
            self._unlock_tree(tree)

    def _select_none_secrets(self, secret_type: str) -> None:
        tree = self._secret_trees.get(secret_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            for secret_id in self._secret_ids_by_type.get(secret_type, []):
                tree.change_state(secret_id, "unchecked")
        finally:
            self._unlock_tree(tree)

    def _unlock_selected_secrets(self, secret_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None or manager is None:
            return
        selected = self._get_checked_or_warn(tree)
        if not selected:
            return
        current_secret_ids = self._collect_unlocked_secrets()
        related_secrets, related_challenges = self._expand_secret_relations(selected)
        new_secret_ids = current_secret_ids | related_secrets
        current_challenge_ids = self._collect_unlocked_challenges()
        new_challenge_ids = current_challenge_ids | related_challenges
        if new_secret_ids == current_secret_ids and new_challenge_ids == current_challenge_ids:
            return
        secret_list = sorted(new_secret_ids, key=lambda value: int(value))
        challenge_list = sorted(new_challenge_ids, key=lambda value: int(value))

        def updater(data: bytes) -> bytes:
            result = script.updateSecrets(data, secret_list)
            if new_challenge_ids != current_challenge_ids:
                result = script.updateChallenges(result, challenge_list)
            return result

        self._apply_update(updater, "비밀을 업데이트하지 못했습니다.")

    def _lock_selected_secrets(self, secret_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None or manager is None:
            return
        selected = self._get_checked_or_warn(tree)
        if not selected:
            return
        current_secret_ids = self._collect_unlocked_secrets()
        related_secrets, related_challenges = self._expand_secret_relations(selected)
        new_secret_ids = current_secret_ids.difference(related_secrets)
        current_challenge_ids = self._collect_unlocked_challenges()
        new_challenge_ids = current_challenge_ids.difference(related_challenges)
        if new_secret_ids == current_secret_ids and new_challenge_ids == current_challenge_ids:
            return
        secret_list = sorted(new_secret_ids, key=lambda value: int(value))
        challenge_list = sorted(new_challenge_ids, key=lambda value: int(value))

        def updater(data: bytes) -> bytes:
            result = script.updateSecrets(data, secret_list)
            if new_challenge_ids != current_challenge_ids:
                result = script.updateChallenges(result, challenge_list)
            return result

        self._apply_update(updater, "비밀을 업데이트하지 못했습니다.")

    def _collect_unlocked_secrets(self) -> Set[str]:
        unlocked: Set[str] = set()
        for manager in self._secret_managers.values():
            for secret_id, info in manager.records.items():
                if info.get("unlock"):
                    unlocked.add(secret_id)
        return unlocked

    def _select_all_items(self, item_type: str) -> None:
        tree = self._item_trees.get(item_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            for item_id in self._item_ids_by_type.get(item_type, []):
                tree.change_state(item_id, "checked")
        finally:
            self._unlock_tree(tree)

    def _select_none_items(self, item_type: str) -> None:
        tree = self._item_trees.get(item_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            for item_id in self._item_ids_by_type.get(item_type, []):
                tree.change_state(item_id, "unchecked")
        finally:
            self._unlock_tree(tree)

    def _unlock_selected_items(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        tree = self._item_trees.get(item_type)
        manager = self._item_managers.get(item_type)
        if tree is None or manager is None:
            return
        selected = self._get_checked_or_warn(tree)
        if not selected:
            return
        unlocked_ids = self._collect_unlocked_items()
        unlocked_ids.update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateItems(data, ids_sorted),
            "아이템을 업데이트하지 못했습니다.",
        )

    def _lock_selected_items(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        tree = self._item_trees.get(item_type)
        manager = self._item_managers.get(item_type)
        if tree is None or manager is None:
            return
        selected = self._get_checked_or_warn(tree)
        if not selected:
            return
        unlocked_ids = self._collect_unlocked_items()
        unlocked_ids.difference_update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateItems(data, ids_sorted),
            "아이템을 업데이트하지 못했습니다.",
        )

    def _collect_unlocked_items(self) -> Set[str]:
        unlocked: Set[str] = set()
        for manager in self._item_managers.values():
            for item_id, info in manager.records.items():
                if info.get("unlock"):
                    unlocked.add(item_id)
        return unlocked

    def _select_all_challenges(self) -> None:
        if self._challenge_tree is None:
            return
        self._lock_tree(self._challenge_tree)
        try:
            for challenge_id in self._challenge_ids:
                self._challenge_tree.change_state(challenge_id, "checked")
        finally:
            self._unlock_tree(self._challenge_tree)

    def _select_none_challenges(self) -> None:
        if self._challenge_tree is None:
            return
        self._lock_tree(self._challenge_tree)
        try:
            for challenge_id in self._challenge_ids:
                self._challenge_tree.change_state(challenge_id, "unchecked")
        finally:
            self._unlock_tree(self._challenge_tree)

    def _unlock_selected_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        if self._challenge_tree is None or self._challenge_manager is None:
            return
        selected = self._get_checked_or_warn(self._challenge_tree)
        if not selected:
            return
        current_challenge_ids = self._collect_unlocked_challenges()
        related_challenges, related_secrets = self._expand_challenge_relations(selected)
        new_challenge_ids = current_challenge_ids | related_challenges
        current_secret_ids = self._collect_unlocked_secrets()
        new_secret_ids = current_secret_ids | related_secrets
        if new_challenge_ids == current_challenge_ids and new_secret_ids == current_secret_ids:
            return
        challenge_list = sorted(new_challenge_ids, key=lambda value: int(value))
        secret_list = sorted(new_secret_ids, key=lambda value: int(value))

        def updater(data: bytes) -> bytes:
            result = script.updateChallenges(data, challenge_list)
            if new_secret_ids != current_secret_ids:
                result = script.updateSecrets(result, secret_list)
            return result

        self._apply_update(updater, "도전과제를 업데이트하지 못했습니다.")

    def _lock_selected_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        if self._challenge_tree is None or self._challenge_manager is None:
            return
        selected = self._get_checked_or_warn(self._challenge_tree)
        if not selected:
            return
        current_challenge_ids = self._collect_unlocked_challenges()
        related_challenges, related_secrets = self._expand_challenge_relations(selected)
        new_challenge_ids = current_challenge_ids.difference(related_challenges)
        current_secret_ids = self._collect_unlocked_secrets()
        new_secret_ids = current_secret_ids.difference(related_secrets)
        if new_challenge_ids == current_challenge_ids and new_secret_ids == current_secret_ids:
            return
        challenge_list = sorted(new_challenge_ids, key=lambda value: int(value))
        secret_list = sorted(new_secret_ids, key=lambda value: int(value))

        def updater(data: bytes) -> bytes:
            result = script.updateChallenges(data, challenge_list)
            if new_secret_ids != current_secret_ids:
                result = script.updateSecrets(result, secret_list)
            return result

        self._apply_update(updater, "도전과제를 업데이트하지 못했습니다.")

    def _collect_unlocked_challenges(self) -> Set[str]:
        if self._challenge_manager is None:
            return set()
        return {
            challenge_id
            for challenge_id, info in self._challenge_manager.records.items()
            if info.get("unlock")
        }

    def _expand_secret_relations(self, secret_ids: Set[str]) -> tuple[Set[str], Set[str]]:
        related_secrets: Set[str] = set()
        related_challenges: Set[str] = set()
        mapping = getattr(self, "_secret_to_challenges", {})
        inverse = getattr(self, "_challenge_to_secrets", {})
        for secret_id in secret_ids:
            related_secrets.add(secret_id)
            for challenge_id in mapping.get(secret_id, set()):
                related_challenges.add(challenge_id)
                related_secrets.update(inverse.get(challenge_id, set()))
        return related_secrets, related_challenges

    def _expand_challenge_relations(self, challenge_ids: Set[str]) -> tuple[Set[str], Set[str]]:
        related_challenges: Set[str] = set()
        related_secrets: Set[str] = set()
        inverse = getattr(self, "_challenge_to_secrets", {})
        for challenge_id in challenge_ids:
            related_challenges.add(challenge_id)
            related_secrets.update(inverse.get(challenge_id, set()))
        return related_challenges, related_secrets

    def _ensure_data_loaded(self) -> bool:
        if self.data is None or not self.filename:
            messagebox.showwarning("파일 없음", "먼저 세이브 파일을 열어주세요.")
            return False
        return True

    def _apply_update(self, updater: Callable[[bytes], bytes], error_message: str) -> bool:
        if self.data is None or not self.filename:
            messagebox.showwarning("파일 없음", "먼저 세이브 파일을 열어주세요.")
            return False
        try:
            new_data = updater(self.data)
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            messagebox.showerror("업데이트 실패", f"{error_message}\n{exc}")
            return False
        updated_with_checksum = script.updateChecksum(new_data)
        try:
            with open(self.filename, "wb") as file:
                file.write(updated_with_checksum)
        except OSError as exc:
            messagebox.showerror("저장 실패", f"세이브 파일을 저장하지 못했습니다.\n{exc}")
            return False
        self.data = updated_with_checksum
        self.refresh_current_values()
        return True
    # ------------------------------------------------------------------
    # Tree refresh helpers
    # ------------------------------------------------------------------
    def _refresh_completion_tab(self) -> None:
        tree = self._completion_tree
        if tree is None:
            return
        if not self._completion_current_mark_ids:
            tree.state(("disabled",))
            return
        if self._current_completion_char_index is None:
            tree.state(("disabled",))
            self._lock_tree(tree)
            try:
                for mark_id in self._completion_current_mark_ids:
                    tree.change_state(mark_id, "unchecked")
            finally:
                self._unlock_tree(tree)
            return
        if self.data is None:
            tree.state(("disabled",))
            self._lock_tree(tree)
            try:
                for mark_id in self._completion_current_mark_ids:
                    tree.change_state(mark_id, "unchecked")
            finally:
                self._unlock_tree(tree)
            return
        tree.state(("!disabled",))
        try:
            values = script.getChecklistUnlocks(self.data, self._current_completion_char_index)
        except Exception:
            values = []
        unlocked_ids = {
            str(index): True
            for index, value in enumerate(values)
            if value
        }
        self._lock_tree(tree)
        try:
            for mark_id in self._completion_current_mark_ids:
                if unlocked_ids.get(mark_id):
                    tree.change_state(mark_id, "checked")
                else:
                    tree.change_state(mark_id, "unchecked")
        finally:
            self._unlock_tree(tree)

    def _refresh_secrets_tab(self) -> None:
        if not self._secret_managers:
            return
        if self.data is None:
            unlocked_ids: Set[str] = set()
        else:
            try:
                secrets = script.getSecrets(self.data)
            except Exception:
                secrets = []
            unlocked_ids = {str(index + 1) for index, value in enumerate(secrets) if value != 0}
        for secret_type, manager in self._secret_managers.items():
            tree = self._secret_trees.get(secret_type)
            if tree is None:
                continue
            self._lock_tree(tree)
            try:
                for secret_id in manager.records:
                    unlocked = secret_id in unlocked_ids
                    manager.set_unlock(secret_id, unlocked)
                    tree.change_state(secret_id, "unchecked")
            finally:
                self._unlock_tree(tree)
            manager.resort()

    def _refresh_items_tab(self) -> None:
        if not self._item_managers:
            return
        if self.data is None:
            unlocked_ids: Set[str] = set()
        else:
            try:
                items = script.getItems(self.data)
            except Exception:
                items = []
            unlocked_ids = {str(index + 1) for index, value in enumerate(items) if value != 0}
        for item_type, tree in self._item_trees.items():
            manager = self._item_managers.get(item_type)
            if manager is None:
                continue
            self._lock_tree(tree)
            try:
                for item_id in manager.records:
                    unlocked = item_id in unlocked_ids
                    manager.set_unlock(item_id, unlocked)
                    tree.change_state(item_id, "unchecked")
            finally:
                self._unlock_tree(tree)
            manager.resort()

    def _refresh_challenges_tab(self) -> None:
        if self._challenge_tree is None or self._challenge_manager is None:
            return
        if self.data is None:
            unlocked_ids: Set[str] = set()
        else:
            try:
                challenges = script.getChallenges(self.data)
            except Exception:
                challenges = []
            unlocked_ids = {str(index + 1) for index, value in enumerate(challenges) if value != 0}
        self._lock_tree(self._challenge_tree)
        try:
            for challenge_id in self._challenge_manager.records:
                unlocked = challenge_id in unlocked_ids
                self._challenge_manager.set_unlock(challenge_id, unlocked)
                self._challenge_tree.change_state(challenge_id, "unchecked")
        finally:
            self._unlock_tree(self._challenge_tree)
        self._challenge_manager.resort()
    # ------------------------------------------------------------------
    # Numeric field helpers and file handling
    # ------------------------------------------------------------------
    def _build_numeric_section(
        self,
        container: ttk.Frame,
        row: int,
        title: str,
        current_var: tk.StringVar,
        entry_var: tk.StringVar,
        command: Callable[[], None],
        is_first: bool = False,
    ) -> None:
        section = ttk.LabelFrame(container, text=title, padding=(12, 10))
        pady = (15, 0) if is_first else (10, 0)
        section.grid(column=0, row=row, sticky="ew", pady=pady)
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="현재값 (Current):").grid(column=0, row=0, sticky="w")
        ttk.Label(section, textvariable=current_var).grid(column=1, row=0, sticky="w")

        ttk.Label(section, text="새 값 (New Value):").grid(column=0, row=1, sticky="w", pady=(8, 0))
        entry = ttk.Entry(section, textvariable=entry_var, width=12)
        entry.grid(column=1, row=1, sticky="w", pady=(8, 0))

        apply_button = ttk.Button(section, text="적용 (Apply)", command=command)
        apply_button.grid(column=2, row=1, sticky="e", padx=(10, 0), pady=(8, 0))

    def _select_source_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="원본 세이브파일 선택",
            initialdir=self._get_initial_directory(),
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return
        normalized = self._normalize_save_path(filename)
        if self.target_save_path:
            source_name = os.path.basename(normalized)
            target_name = os.path.basename(self.target_save_path)
            if source_name != target_name:
                messagebox.showerror("경고", "파일 이름이 다릅니다.")
                return
        self.source_save_path = normalized
        self.settings["source_save_path"] = normalized
        self._update_source_display()
        self._save_settings()
        self._apply_auto_overwrite_if_enabled(show_message=True)

    def _select_target_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="덮어쓰기할 세이브파일 선택",
            initialdir=self._get_initial_directory(),
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return
        normalized = self._normalize_save_path(filename)
        if not self._path_contains_steam(normalized):
            proceed = messagebox.askyesno(
                "경로 확인",
                "아이작 세이브파일 경로가 아닌 것 같습니다. 그래도 계속하시겠습니까?",
            )
            if not proceed:
                return
        if self.source_save_path:
            source_name = os.path.basename(self.source_save_path)
            target_name = os.path.basename(normalized)
            if source_name != target_name:
                messagebox.showerror("경고", "파일 이름이 다릅니다.")
                return
        self.target_save_path = normalized
        self.settings["target_save_path"] = normalized
        self._update_target_display()
        self._save_settings()
        self._apply_auto_overwrite_if_enabled(show_message=True)

    def _on_auto_set_999_toggle(self) -> None:
        enabled = bool(self.auto_set_999_var.get())
        self.settings["auto_set_999"] = enabled
        self._save_settings()
        if enabled:
            self._apply_auto_999_if_needed()

    def _on_auto_overwrite_toggle(self) -> None:
        enabled = bool(self.auto_overwrite_var.get())
        self.settings["auto_overwrite"] = enabled
        self._save_settings()
        if enabled:
            self._apply_auto_overwrite_if_enabled(show_message=True)

    def _show_auto_overwrite_help(self) -> None:
        help_window = tk.Toplevel(self)
        help_window.title("세이브파일 자동 덮어쓰기 안내")
        help_window.transient(self)
        help_window.resizable(False, False)

        container = ttk.Frame(help_window, padding=(20, 16, 20, 16))
        container.grid(sticky="nsew")
        help_window.columnconfigure(0, weight=1)
        help_window.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        base_font = tkfont.nametofont("TkDefaultFont")
        base_size = abs(int(base_font.cget("size")))
        title_font = base_font.copy()
        title_font.configure(size=max(base_size + 2, 12), weight="bold")
        body_font = base_font.copy()
        body_font.configure(size=max(base_size + 1, 11))

        title_label = ttk.Label(
            container,
            text="자동 덮어쓰기 사용 방법",
            font=title_font,
            justify="left",
        )
        title_label.grid(column=0, row=0, sticky="w")

        steps = (
            "1. '원본 세이브파일 열기' 버튼을 눌러 기준이 되는 세이브파일을 선택하세요.",
            "2. '덮어쓰기할 세이브파일 열기' 버튼을 눌러 실제 게임 세이브파일을 선택하세요.",
            "3. '세이브파일 자동 덮어쓰기'를 체크하면 경로가 저장되고, 프로그램 실행 시 원본 세이브파일이 자동으로 덮어쓰기 경로에 복사됩니다.",
        )
        body_label = ttk.Label(
            container,
            text="\n\n".join(steps),
            font=body_font,
            justify="left",
            wraplength=460,
        )
        body_label.grid(column=0, row=1, sticky="w", pady=(12, 18))

        close_button = ttk.Button(container, text="확인", command=help_window.destroy)
        close_button.grid(column=0, row=2, sticky="e")
        close_button.focus_set()

        help_window.bind("<Escape>", lambda event: help_window.destroy())

        help_window.update_idletasks()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty()
        root_width = self.winfo_width()
        root_height = self.winfo_height()
        window_width = help_window.winfo_width()
        window_height = help_window.winfo_height()

        pos_x = root_x + (root_width - window_width) // 2
        pos_y = root_y + (root_height - window_height) // 2
        help_window.geometry(f"+{pos_x}+{pos_y}")

    def _apply_auto_999_if_needed(self) -> None:
        if not bool(self.auto_set_999_var.get()):
            return
        if self.data is None or not self.filename:
            return
        self.set_donation_greed_eden_to_max(auto_trigger=True)

    def _apply_auto_overwrite_if_enabled(self, *, show_message: bool = False) -> None:
        if not bool(self.auto_overwrite_var.get()):
            return
        if not self.source_save_path or not self.target_save_path:
            return
        self._overwrite_target_save(show_message=show_message)

    def _overwrite_target_save(self, *, show_message: bool) -> None:
        source = self.source_save_path
        target = self.target_save_path
        if not source or not target:
            if show_message:
                messagebox.showwarning(
                    "경로 없음",
                    "원본과 덮어쓸 세이브파일을 모두 선택해주세요.",
                )
            return
        if not os.path.exists(source):
            messagebox.showerror("덮어쓰기 실패", "원본 세이브파일을 찾을 수 없습니다.")
            return
        target_dir = os.path.dirname(target)
        if target_dir and not os.path.exists(target_dir):
            messagebox.showerror("덮어쓰기 실패", "덮어쓸 세이브파일 경로를 찾을 수 없습니다.")
            return
        try:
            shutil.copyfile(source, target)
        except OSError as exc:
            messagebox.showerror("덮어쓰기 실패", f"세이브파일을 덮어쓰지 못했습니다.\n{exc}")
            return
        if show_message:
            messagebox.showinfo("덮어쓰기 완료", "원본 세이브파일을 덮어썼습니다.")

    def open_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="아이작 세이브파일 선택",
            initialdir=self._get_initial_directory(),
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return
        self._load_file(filename)

    def _get_initial_directory(self) -> str:
        last_path_setting = self.settings.get("last_path")
        if isinstance(last_path_setting, str) and last_path_setting:
            candidate_dir = os.path.dirname(last_path_setting)
            if candidate_dir and os.path.exists(candidate_dir):
                return candidate_dir
        initdir = os.getcwd()
        for env_var in ("ProgramFiles(x86)", "ProgramFiles"):
            base_path = os.environ.get(env_var)
            if not base_path:
                continue
            candidate = os.path.join(base_path, "Steam", "userdata")
            if os.path.exists(candidate):
                return candidate
        return initdir

    def _load_file(self, filename: str, *, show_errors: bool = True) -> bool:
        normalized = os.path.abspath(filename)
        try:
            with open(normalized, "rb") as file:
                data = file.read()
        except OSError as exc:
            if show_errors:
                messagebox.showerror("파일 오류", f"세이브 파일을 열 수 없습니다.\n{exc}")
            return False

        self.data = data
        self.filename = normalized
        basename = os.path.basename(normalized)
        self.loaded_file_var.set(f"불러온 파일 (Loaded File): {basename}")
        self.settings["last_path"] = normalized
        self._save_settings()
        self.refresh_current_values()
        self._apply_auto_999_if_needed()
        return True

    def _on_remember_path_toggle(self) -> None:
        self.settings["remember_path"] = bool(self.remember_path_var.get())
        if self.settings["remember_path"] and self.filename:
            self.settings["last_path"] = self.filename
        self._save_settings()

    def _open_remembered_file_if_available(self) -> None:
        if not bool(self.remember_path_var.get()):
            return
        last_path_setting = self.settings.get("last_path")
        if not isinstance(last_path_setting, str) or not last_path_setting:
            return
        if not os.path.exists(last_path_setting):
            messagebox.showwarning(
                "자동 열기 실패",
                "저장된 세이브 파일 경로를 찾을 수 없습니다. 새로 선택해주세요.",
            )
            self.loaded_file_var.set(self._default_loaded_text)
            return
        if not self._load_file(last_path_setting, show_errors=False):
            messagebox.showwarning(
                "자동 열기 실패",
                "저장된 세이브 파일을 불러오지 못했습니다. 파일이 사용 중인지 확인해주세요.",
            )
            self.loaded_file_var.set(self._default_loaded_text)

    def _perform_startup_tasks(self) -> None:
        self._open_remembered_file_if_available()
        self._apply_auto_overwrite_if_enabled()

    def _load_settings(self) -> Dict[str, object]:
        settings = DEFAULT_SETTINGS.copy()
        try:
            with self.settings_path.open(encoding="utf-8") as file:
                loaded = json.load(file)
        except (OSError, json.JSONDecodeError):
            return settings
        if isinstance(loaded, dict):
            remember = loaded.get("remember_path")
            if isinstance(remember, bool):
                settings["remember_path"] = remember
            last_path = loaded.get("last_path")
            if isinstance(last_path, str):
                settings["last_path"] = last_path
            auto_999 = loaded.get("auto_set_999")
            if isinstance(auto_999, bool):
                settings["auto_set_999"] = auto_999
            auto_overwrite = loaded.get("auto_overwrite")
            if isinstance(auto_overwrite, bool):
                settings["auto_overwrite"] = auto_overwrite
            source_path = loaded.get("source_save_path")
            if isinstance(source_path, str):
                settings["source_save_path"] = source_path
            target_path = loaded.get("target_save_path")
            if isinstance(target_path, str):
                settings["target_save_path"] = target_path
        return settings

    def _save_settings(self) -> None:
        settings_to_save = DEFAULT_SETTINGS.copy()
        settings_to_save["remember_path"] = bool(self.remember_path_var.get())
        last_path_setting = self.settings.get("last_path")
        if isinstance(last_path_setting, str):
            settings_to_save["last_path"] = last_path_setting
        auto_set_var = getattr(self, "auto_set_999_var", None)
        auto_overwrite_var = getattr(self, "auto_overwrite_var", None)
        settings_to_save["auto_set_999"] = bool(auto_set_var.get()) if auto_set_var else False
        settings_to_save["auto_overwrite"] = bool(auto_overwrite_var.get()) if auto_overwrite_var else False
        settings_to_save["source_save_path"] = self.source_save_path
        settings_to_save["target_save_path"] = self.target_save_path
        self.settings = settings_to_save
        try:
            with self.settings_path.open("w", encoding="utf-8") as file:
                json.dump(settings_to_save, file, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _read_numeric_value(self, key: str) -> Optional[int]:
        if self.data is None:
            return None
        config = self._numeric_config.get(key)
        if config is None:
            return None
        try:
            section_offsets = script.getSectionOffsets(self.data)
        except Exception:
            return None
        try:
            base_offset = section_offsets[1] + 0x4 + int(config["offset"])
            return int(script.getInt(self.data, base_offset))
        except Exception:
            return None

    def apply_field(
        self, key: str, preset: int | None = None, *, preserve_entry: bool = False
    ) -> bool:
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

        self.refresh_current_values(update_entry=not preserve_entry)
        return True

    def set_donation_greed_eden_to_max(self, *, auto_trigger: bool = False) -> None:
        if self.data is None or not self.filename:
            if not auto_trigger:
                messagebox.showwarning("파일 없음", "먼저 세이브 파일을 열어주세요.")
            return
        original_streak = self._read_numeric_value("streak")

        for field_key in ("donation", "greed", "eden"):
            if not self.apply_field(
                field_key, preset=999, preserve_entry=not auto_trigger
            ):
                break

        if original_streak is None:
            return

        current_streak = self._read_numeric_value("streak")
        if current_streak is not None and current_streak != original_streak:
            self.apply_field(
                "streak", preset=original_streak, preserve_entry=not auto_trigger
            )

    def refresh_current_values(self, *, update_entry: bool = True) -> None:
        if self.data is None:
            for key in self._numeric_order:
                vars_map = self._numeric_vars[key]
                vars_map["current"].set("0")
                if update_entry:
                    vars_map["entry"].set("0")
            self._refresh_completion_tab()
            self._refresh_secrets_tab()
            self._refresh_items_tab()
            self._refresh_challenges_tab()
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
            if update_entry:
                vars_map["entry"].set(value_str)

        self._refresh_completion_tab()
        self._refresh_secrets_tab()
        self._refresh_items_tab()
        self._refresh_challenges_tab()

def main() -> None:
    app = IsaacSaveEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
