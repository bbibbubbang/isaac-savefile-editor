"""New Tkinter-based interface for The Binding of Isaac save editor.

This module provides a refreshed GUI with tab structure and a main tab that
allows users to edit key numeric values such as donation machine totals and
win streaks. It replaces the legacy ``gui.py`` entry point for everyday use
while keeping existing backend logic in ``script.py``.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional, Set

from ttkwidgets import CheckboxTreeview

import script


DATA_DIR = Path(__file__).resolve().parent


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

    MAIN_TAB_NAMES: List[str] = [
        "메인",
        "완료 마크",
        "비밀",
        "패시브",
        "액티브",
        "도전과제",
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

        self._locked_tree_ids: Set[int] = set()

        self._completion_data = self._load_completion_data()
        self._character_options = self._build_character_options()
        self._current_character_id: Optional[str] = self._character_options[0][1] if self._character_options else None
        self._character_var = tk.StringVar()
        self._completion_tree: Optional[CheckboxTreeview] = None
        self._completion_manager: Optional[TreeManager] = None

        self._secret_records = self._load_secret_records()
        self._secret_tree: Optional[CheckboxTreeview] = None
        self._secret_manager: Optional[TreeManager] = None
        self._secret_ids: List[str] = [record["iid"] for record in self._secret_records]

        self._item_records, self._item_ids_by_type = self._load_item_records()
        self._item_trees: Dict[str, CheckboxTreeview] = {}
        self._item_managers: Dict[str, TreeManager] = {}

        self._challenge_records = self._load_challenge_records()
        self._challenge_tree: Optional[CheckboxTreeview] = None
        self._challenge_manager: Optional[TreeManager] = None
        self._challenge_ids: List[str] = [record["iid"] for record in self._challenge_records]

        self._build_layout()
        self.refresh_current_values()
    # ------------------------------------------------------------------
    # Layout construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.notebook = notebook

        main_tab = ttk.Frame(notebook, padding=12)
        main_tab.columnconfigure(0, weight=1)
        notebook.add(main_tab, text=self.MAIN_TAB_NAMES[0])
        self._build_main_tab(main_tab)

        completion_tab = ttk.Frame(notebook, padding=12)
        completion_tab.columnconfigure(0, weight=1)
        completion_tab.rowconfigure(1, weight=1)
        notebook.add(completion_tab, text=self.MAIN_TAB_NAMES[1])
        self._build_completion_tab(completion_tab)

        secrets_tab = ttk.Frame(notebook, padding=12)
        secrets_tab.columnconfigure(0, weight=1)
        secrets_tab.rowconfigure(1, weight=1)
        notebook.add(secrets_tab, text=self.MAIN_TAB_NAMES[2])
        self._build_secrets_tab(secrets_tab)

        passive_tab = ttk.Frame(notebook, padding=12)
        passive_tab.columnconfigure(0, weight=1)
        passive_tab.rowconfigure(1, weight=1)
        notebook.add(passive_tab, text=self.MAIN_TAB_NAMES[3])
        self._build_item_tab(passive_tab, "Passive")

        active_tab = ttk.Frame(notebook, padding=12)
        active_tab.columnconfigure(0, weight=1)
        active_tab.rowconfigure(1, weight=1)
        notebook.add(active_tab, text=self.MAIN_TAB_NAMES[4])
        self._build_item_tab(active_tab, "Active")

        challenge_tab = ttk.Frame(notebook, padding=12)
        challenge_tab.columnconfigure(0, weight=1)
        challenge_tab.rowconfigure(1, weight=1)
        notebook.add(challenge_tab, text=self.MAIN_TAB_NAMES[5])
        self._build_challenges_tab(challenge_tab)

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

    def _build_completion_tab(self, container: ttk.Frame) -> None:
        selection_frame = ttk.Frame(container)
        selection_frame.grid(column=0, row=0, sticky="ew")
        selection_frame.columnconfigure(1, weight=1)

        ttk.Label(selection_frame, text="캐릭터 선택:").grid(column=0, row=0, sticky="w")
        combo = ttk.Combobox(selection_frame, state="readonly", textvariable=self._character_var)
        combo.grid(column=1, row=0, sticky="w", padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", self._on_character_selected)

        button_frame = ttk.Frame(selection_frame)
        button_frame.grid(column=2, row=0, sticky="e")
        ttk.Button(
            button_frame,
            text="모두 선택 (Select All)",
            command=self._select_all_completion_marks,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_frame,
            text="모두 해제 (Select None)",
            command=self._select_none_completion_marks,
        ).pack(side="left")

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=1, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_tree(tree_container, ("unlock",))
        tree.column("#0", anchor="w", width=320, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", text="이름 (Name)", command=lambda m=manager: m.sort("name"))
        tree.heading("unlock", text="해금 여부 (Unlock)", command=lambda m=manager: m.sort("unlock"))

        self._completion_tree = tree
        self._completion_manager = manager
        self._bind_checkbox_handler(tree, self._handle_completion_toggle)

        values = [label for label, _ in self._character_options]
        combo["values"] = values
        if self._current_character_id and values:
            combo.current(0)
            self._character_var.set(values[0])
        self._populate_completion_tree()

    def _build_secrets_tab(self, container: ttk.Frame) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")
        ttk.Button(
            button_frame,
            text="모두 선택 (Select All)",
            command=self._select_all_secrets,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            button_frame,
            text="모두 해제 (Select None)",
            command=self._select_none_secrets,
        ).pack(side="left")

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=1, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_tree(tree_container, ("unlock",))
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", text="이름 (Name)", command=lambda m=manager: m.sort("name"))
        tree.heading("unlock", text="해금 여부 (Unlock)", command=lambda m=manager: m.sort("unlock"))

        records: Dict[str, Dict[str, object]] = {}
        for record in self._secret_records:
            tree.insert("", "end", iid=record["iid"], text=record["display"], values=("X",))
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record["name_sort"],
                "unlock": False,
                "quality": None,
            }
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._secret_tree = tree
        self._secret_manager = manager
        self._bind_checkbox_handler(tree, self._handle_secret_toggle)

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
        self._bind_checkbox_handler(tree, lambda t=item_type: self._handle_item_toggle(t))

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

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=1, sticky="nsew", pady=(12, 0))
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
        self._bind_checkbox_handler(tree, self._handle_challenge_toggle)

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

    def _populate_completion_tree(self) -> None:
        if self._completion_tree is None or self._completion_manager is None:
            return
        char_id = self._current_character_id
        marks = self._completion_data.get(char_id, {}).get("marks", []) if char_id is not None else []

        self._lock_tree(self._completion_tree)
        try:
            self._completion_tree.delete(*self._completion_tree.get_children(""))
            records: Dict[str, Dict[str, object]] = {}
            for mark in marks:
                iid = mark["iid"]
                self._completion_tree.insert("", "end", iid=iid, text=mark["display"], values=("X",))
                records[iid] = {
                    "iid": iid,
                    "name_sort": mark["name_sort"],
                    "unlock": False,
                    "quality": None,
                    "index": mark["index"],
                }
            self._completion_manager.records = records
        finally:
            self._unlock_tree(self._completion_tree)
        self._completion_manager.sort("name", ascending=True, update_toggle=False)

    def _bind_checkbox_handler(self, tree: CheckboxTreeview, callback: Callable[[], None]) -> None:
        def handler(event: tk.Event) -> None:  # type: ignore[override]
            if self._is_tree_locked(tree):
                return
            element = tree.identify("element", event.x, event.y)
            if "image" not in element:
                return
            self.after_idle(callback)

        tree.bind("<ButtonRelease-1>", handler, add="+")

    def _lock_tree(self, tree: CheckboxTreeview) -> None:
        self._locked_tree_ids.add(id(tree))

    def _unlock_tree(self, tree: CheckboxTreeview) -> None:
        self._locked_tree_ids.discard(id(tree))

    def _is_tree_locked(self, tree: CheckboxTreeview) -> bool:
        return id(tree) in self._locked_tree_ids
    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_completion_data(self) -> Dict[str, Dict[str, object]]:
        data: Dict[str, Dict[str, object]] = {}
        csv_path = DATA_DIR / "ui_completion_marks.csv"
        if not csv_path.exists():
            return data
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                char_id = (row.get("CharacterIndex") or "").strip()
                if not char_id:
                    continue
                char_info = data.setdefault(
                    char_id,
                    {
                        "english": (row.get("CharacterName") or "").strip(),
                        "korean": (row.get("Korean") or "").strip(),
                        "marks": [],
                    },
                )
                mark_index = (row.get("MarkIndex") or "").strip()
                mark_name = (row.get("MarkName") or "").strip()
                if not mark_index:
                    continue
                try:
                    index_value = int(mark_index)
                except ValueError:
                    index_value = len(char_info["marks"])  # type: ignore[arg-type]
                display = mark_name or mark_index
                char_info["marks"].append(
                    {
                        "iid": mark_index,
                        "display": display,
                        "name_sort": display.lower(),
                        "index": index_value,
                    }
                )
        for info in data.values():
            info["marks"].sort(key=lambda mark: int(mark.get("index", 0)))  # type: ignore[arg-type]
        return data

    def _build_character_options(self) -> List[tuple[str, str]]:
        options: List[tuple[str, str]] = []
        for char_id, info in sorted(self._completion_data.items(), key=lambda item: int(item[0])):
            english = str(info.get("english", ""))
            korean = str(info.get("korean", ""))
            if korean and english and korean != english:
                label = f"{korean} ({english})"
            else:
                label = korean or english or char_id
            options.append((label, char_id))
        return options

    def _load_secret_records(self) -> List[Dict[str, str]]:
        csv_path = DATA_DIR / "ui_secrets.csv"
        records: List[Dict[str, str]] = []
        if not csv_path.exists():
            return records
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                secret_id = (row.get("SecretID") or "").strip()
                if not secret_id:
                    continue
                korean = (row.get("Korean") or "").strip()
                unlock_name = (row.get("UnlockName") or "").strip()
                secret_name = (row.get("SecretName") or "").strip()
                primary = korean or unlock_name or secret_name or secret_id
                if unlock_name and primary != unlock_name:
                    display = f"{primary} ({unlock_name})"
                elif secret_name and primary != secret_name:
                    display = f"{primary} ({secret_name})"
                else:
                    display = primary
                records.append(
                    {
                        "iid": secret_id,
                        "display": display,
                        "name_sort": display.lower(),
                    }
                )
        return records

    def _load_item_records(self) -> tuple[Dict[str, Dict[str, Dict[str, object]]], Dict[str, List[str]]]:
        csv_path = DATA_DIR / "ui_items.csv"
        records: Dict[str, Dict[str, Dict[str, object]]] = {"Passive": {}, "Active": {}}
        ids_by_type: Dict[str, List[str]] = {"Passive": [], "Active": []}
        if not csv_path.exists():
            return records, ids_by_type
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
                records[item_type][item_id] = {
                    "iid": item_id,
                    "display": display,
                    "name_sort": display.lower(),
                    "quality": quality_value,
                }
                ids_by_type[item_type].append(item_id)
        return records, ids_by_type

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
                    }
                )
        return records
    # ------------------------------------------------------------------
    # Event handlers and select helpers
    # ------------------------------------------------------------------
    def _on_character_selected(self, event: tk.Event) -> None:  # type: ignore[override]
        value = self._character_var.get()
        for label, char_id in self._character_options:
            if label == value:
                self._current_character_id = char_id
                break
        else:
            self._current_character_id = None
        self._populate_completion_tree()
        self._refresh_completion_tab()

    def _handle_completion_toggle(self) -> None:
        if not self._ensure_data_loaded():
            self.refresh_current_values()
            return
        if self._completion_tree is None or self._completion_manager is None:
            return
        char_id = self._current_character_id
        if char_id is None:
            return
        checked = set(self._completion_tree.get_checked())
        marks = self._completion_data.get(char_id, {}).get("marks", [])
        length = max((int(mark["index"]) for mark in marks), default=-1) + 1
        new_data = [0] * max(length, len(marks))
        for mark in marks:
            iid = mark["iid"]
            index = int(mark["index"])
            if iid in checked:
                new_data[index] = 2
        if self._apply_update(
            lambda data: script.updateCheckListUnlocks(data, int(char_id), new_data),
            "완료 마크를 업데이트하지 못했습니다.",
        ):
            for mark in marks:
                unlocked = mark["iid"] in checked
                self._completion_manager.set_unlock(mark["iid"], unlocked)
            self._completion_manager.resort()

    def _handle_secret_toggle(self) -> None:
        if not self._ensure_data_loaded():
            self.refresh_current_values()
            return
        if self._secret_tree is None or self._secret_manager is None:
            return
        checked = sorted(self._secret_tree.get_checked(), key=lambda value: int(value))
        if self._apply_update(
            lambda data: script.updateSecrets(data, checked),
            "비밀을 업데이트하지 못했습니다.",
        ):
            unlocked_set = set(checked)
            for secret_id in self._secret_manager.records:
                self._secret_manager.set_unlock(secret_id, secret_id in unlocked_set)
            self._secret_manager.resort()

    def _handle_item_toggle(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            self.refresh_current_values()
            return
        checked = sorted(self._gather_checked_item_ids(), key=lambda value: int(value))
        if self._apply_update(
            lambda data: script.updateItems(data, checked),
            "아이템을 업데이트하지 못했습니다.",
        ):
            unlocked_set = set(checked)
            for tree_type, manager in self._item_managers.items():
                for item_id in manager.records:
                    manager.set_unlock(item_id, item_id in unlocked_set)
                manager.resort()

    def _handle_challenge_toggle(self) -> None:
        if not self._ensure_data_loaded():
            self.refresh_current_values()
            return
        if self._challenge_tree is None or self._challenge_manager is None:
            return
        checked = sorted(self._challenge_tree.get_checked(), key=lambda value: int(value))
        if self._apply_update(
            lambda data: script.updateChallenges(data, checked),
            "도전과제를 업데이트하지 못했습니다.",
        ):
            unlocked_set = set(checked)
            for challenge_id in self._challenge_manager.records:
                self._challenge_manager.set_unlock(challenge_id, challenge_id in unlocked_set)
            self._challenge_manager.resort()

    def _select_all_completion_marks(self) -> None:
        if not self._ensure_data_loaded():
            return
        char_id = self._current_character_id
        if char_id is None:
            return
        marks = self._completion_data.get(char_id, {}).get("marks", [])
        length = max((int(mark["index"]) for mark in marks), default=-1) + 1
        new_data = [2] * max(length, len(marks))
        self._apply_update(
            lambda data: script.updateCheckListUnlocks(data, int(char_id), new_data),
            "완료 마크를 업데이트하지 못했습니다.",
        )

    def _select_none_completion_marks(self) -> None:
        if not self._ensure_data_loaded():
            return
        char_id = self._current_character_id
        if char_id is None:
            return
        marks = self._completion_data.get(char_id, {}).get("marks", [])
        length = max((int(mark["index"]) for mark in marks), default=-1) + 1
        new_data = [0] * max(length, len(marks))
        self._apply_update(
            lambda data: script.updateCheckListUnlocks(data, int(char_id), new_data),
            "완료 마크를 업데이트하지 못했습니다.",
        )

    def _select_all_secrets(self) -> None:
        if not self._ensure_data_loaded():
            return
        ids_sorted = sorted(self._secret_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateSecrets(data, ids_sorted),
            "비밀을 업데이트하지 못했습니다.",
        )

    def _select_none_secrets(self) -> None:
        if not self._ensure_data_loaded():
            return
        self._apply_update(
            lambda data: script.updateSecrets(data, []),
            "비밀을 업데이트하지 못했습니다.",
        )

    def _select_all_items(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        checked = self._gather_checked_item_ids()
        checked.update(self._item_ids_by_type.get(item_type, []))
        ids_sorted = sorted(checked, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateItems(data, ids_sorted),
            "아이템을 업데이트하지 못했습니다.",
        )

    def _select_none_items(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        checked = self._gather_checked_item_ids()
        for item_id in self._item_ids_by_type.get(item_type, []):
            checked.discard(item_id)
        ids_sorted = sorted(checked, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateItems(data, ids_sorted),
            "아이템을 업데이트하지 못했습니다.",
        )

    def _select_all_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        ids_sorted = sorted(self._challenge_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateChallenges(data, ids_sorted),
            "도전과제를 업데이트하지 못했습니다.",
        )

    def _select_none_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        self._apply_update(
            lambda data: script.updateChallenges(data, []),
            "도전과제를 업데이트하지 못했습니다.",
        )

    def _gather_checked_item_ids(self) -> Set[str]:
        checked: Set[str] = set()
        for tree in self._item_trees.values():
            checked.update(tree.get_checked())
        return checked

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
        if self._completion_tree is None or self._completion_manager is None:
            return
        char_id = self._current_character_id
        marks = self._completion_data.get(char_id, {}).get("marks", []) if char_id is not None else []
        if self.data is None or char_id is None:
            checklist = [0] * len(marks)
        else:
            try:
                checklist = script.getChecklistUnlocks(self.data, int(char_id))
            except Exception:
                checklist = [0] * len(marks)
        self._lock_tree(self._completion_tree)
        try:
            for mark in marks:
                index = int(mark["index"])
                unlocked = index < len(checklist) and checklist[index] != 0
                self._completion_tree.change_state(mark["iid"], "checked" if unlocked else "unchecked")
                self._completion_manager.set_unlock(mark["iid"], unlocked)
        finally:
            self._unlock_tree(self._completion_tree)
        self._completion_manager.resort()

    def _refresh_secrets_tab(self) -> None:
        if self._secret_tree is None or self._secret_manager is None:
            return
        if self.data is None:
            unlocked_ids: Set[str] = set()
        else:
            try:
                secrets = script.getSecrets(self.data)
            except Exception:
                secrets = []
            unlocked_ids = {str(index + 1) for index, value in enumerate(secrets) if value != 0}
        self._lock_tree(self._secret_tree)
        try:
            for secret_id in self._secret_manager.records:
                unlocked = secret_id in unlocked_ids
                self._secret_tree.change_state(secret_id, "checked" if unlocked else "unchecked")
                self._secret_manager.set_unlock(secret_id, unlocked)
        finally:
            self._unlock_tree(self._secret_tree)
        self._secret_manager.resort()

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
                    tree.change_state(item_id, "checked" if unlocked else "unchecked")
                    manager.set_unlock(item_id, unlocked)
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
                self._challenge_tree.change_state(challenge_id, "checked" if unlocked else "unchecked")
                self._challenge_manager.set_unlock(challenge_id, unlocked)
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
