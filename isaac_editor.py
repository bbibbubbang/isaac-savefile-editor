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
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional, Set

from ttkwidgets import CheckboxTreeview

import script


DATA_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = DATA_DIR / "settings.json"
DEFAULT_SETTINGS: Dict[str, object] = {
    "remember_path": False,
    "last_path": "",
}


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
        "Item": "업적아이템",
        "Boss": "보스",
        "Card": "카드",
        "Rune": "룬",
        "Pill": "알약",
        "Trinket": "장신구",
        "None": "무효과",
        "Other": "기타",
        "Pickup": "픽업",
    }
    SECRET_FALLBACK_TYPE = "Other"

    def __init__(self) -> None:
        super().__init__()
        self.title("Isaac Savefile Editor")

        self.filename: str = ""
        self.data: bytes | None = None

        self.settings_path = SETTINGS_PATH
        self.settings = self._load_settings()
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
            self._secret_records_by_type,
            self._secret_ids_by_type,
            self._secret_tab_labels,
            self._secret_tab_order,
        ) = self._load_secret_records()
        self._secret_trees: Dict[str, CheckboxTreeview] = {}
        self._secret_managers: Dict[str, TreeManager] = {}

        self._item_records, self._item_ids_by_type = self._load_item_records()
        self._item_trees: Dict[str, CheckboxTreeview] = {}
        self._item_managers: Dict[str, TreeManager] = {}

        self._challenge_records = self._load_challenge_records()
        self._challenge_tree: Optional[CheckboxTreeview] = None
        self._challenge_manager: Optional[TreeManager] = None
        self._challenge_ids: List[str] = [record["iid"] for record in self._challenge_records]

        self._build_layout()
        self.refresh_current_values()
        self.after(0, self._open_remembered_file_if_available)
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

        special_secret_types = {"Item", "None"}
        for secret_type in self._secret_tab_order:
            if secret_type in special_secret_types:
                continue
            if not self._secret_ids_by_type.get(secret_type):
                continue
            tab_label = self._secret_tab_labels.get(secret_type, secret_type)
            secrets_tab = ttk.Frame(notebook, padding=12)
            secrets_tab.columnconfigure(0, weight=1)
            notebook.add(secrets_tab, text=tab_label)
            self._build_secrets_tab(secrets_tab, secret_type)

        passive_tab = ttk.Frame(notebook, padding=12)
        passive_tab.columnconfigure(0, weight=1)
        passive_tab.rowconfigure(1, weight=1)
        notebook.add(passive_tab, text="패시브")
        self._build_item_tab(passive_tab, "Passive")

        active_tab = ttk.Frame(notebook, padding=12)
        active_tab.columnconfigure(0, weight=1)
        active_tab.rowconfigure(1, weight=1)
        notebook.add(active_tab, text="액티브")
        self._build_item_tab(active_tab, "Active")

        challenge_tab = ttk.Frame(notebook, padding=12)
        challenge_tab.columnconfigure(0, weight=1)
        challenge_tab.rowconfigure(1, weight=1)
        notebook.add(challenge_tab, text="도전과제")
        self._build_challenges_tab(challenge_tab)

        if "Item" in self._secret_tab_order and self._secret_ids_by_type.get("Item"):
            tab_label = self._secret_tab_labels.get("Item", "Item")
            achievements_tab = ttk.Frame(notebook, padding=12)
            achievements_tab.columnconfigure(0, weight=1)
            notebook.add(achievements_tab, text=tab_label)
            self._build_secrets_tab(achievements_tab, "Item")

        if "None" in self._secret_tab_order and self._secret_ids_by_type.get("None"):
            tab_label = self._secret_tab_labels.get("None", "None")
            none_tab = ttk.Frame(notebook, padding=12)
            none_tab.columnconfigure(0, weight=1)
            notebook.add(none_tab, text=tab_label)
            self._build_secrets_tab(none_tab, "None")

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

        tree_row = 1
        if secret_type == "Item":
            ttk.Label(
                container,
                text="업적아이템은 모두 해금하고, 패시브/액티브 아이템에서 해금 여부를 변경하세요.",
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
        for record in self._secret_records_by_type.get(secret_type, []):
            tree.insert("", "end", iid=record["iid"], text=record["display"], values=("X",))
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record["name_sort"],
                "unlock": False,
                "quality": None,
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
    def _load_secret_records(
        self,
    ) -> tuple[
        Dict[str, List[Dict[str, str]]],
        Dict[str, List[str]],
        Dict[str, str],
        List[str],
    ]:
        csv_path = DATA_DIR / "ui_secrets.csv"
        records_by_type: Dict[str, List[Dict[str, str]]] = {}
        ids_by_type: Dict[str, List[str]] = {}
        tab_labels: Dict[str, str] = {}
        type_order: List[str] = []
        if not csv_path.exists():
            return records_by_type, ids_by_type, tab_labels, type_order

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
                secret_type = (row.get("Type") or "").strip()
                if not secret_type:
                    secret_type = self.SECRET_FALLBACK_TYPE
                register_type(secret_type)
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
                records_by_type[secret_type].append(
                    {
                        "iid": secret_id,
                        "display": display,
                        "name_sort": display.lower(),
                    }
                )
                ids_by_type[secret_type].append(secret_id)
        return records_by_type, ids_by_type, tab_labels, type_order

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
        unlocked_ids = self._collect_unlocked_secrets()
        unlocked_ids.update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateSecrets(data, ids_sorted),
            "비밀을 업데이트하지 못했습니다.",
        )

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
        unlocked_ids = self._collect_unlocked_secrets()
        unlocked_ids.difference_update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateSecrets(data, ids_sorted),
            "비밀을 업데이트하지 못했습니다.",
        )

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
        unlocked_ids = self._collect_unlocked_challenges()
        unlocked_ids.update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateChallenges(data, ids_sorted),
            "도전과제를 업데이트하지 못했습니다.",
        )

    def _lock_selected_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        if self._challenge_tree is None or self._challenge_manager is None:
            return
        selected = self._get_checked_or_warn(self._challenge_tree)
        if not selected:
            return
        unlocked_ids = self._collect_unlocked_challenges()
        unlocked_ids.difference_update(selected)
        ids_sorted = sorted(unlocked_ids, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.updateChallenges(data, ids_sorted),
            "도전과제를 업데이트하지 못했습니다.",
        )

    def _collect_unlocked_challenges(self) -> Set[str]:
        if self._challenge_manager is None:
            return set()
        return {
            challenge_id
            for challenge_id, info in self._challenge_manager.records.items()
            if info.get("unlock")
        }

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
        return settings

    def _save_settings(self) -> None:
        settings_to_save = DEFAULT_SETTINGS.copy()
        settings_to_save["remember_path"] = bool(self.remember_path_var.get())
        last_path_setting = self.settings.get("last_path")
        if isinstance(last_path_setting, str):
            settings_to_save["last_path"] = last_path_setting
        self.settings = settings_to_save
        try:
            with self.settings_path.open("w", encoding="utf-8") as file:
                json.dump(settings_to_save, file, ensure_ascii=False, indent=2)
        except OSError:
            pass

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

        self._refresh_secrets_tab()
        self._refresh_items_tab()
        self._refresh_challenges_tab()

def main() -> None:
    app = IsaacSaveEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
