"""New Tkinter-based interface for The Binding of Isaac save editor.

This module provides a refreshed GUI with tab structure and a main tab that
allows users to edit key numeric values such as donation machine totals and
win streaks. It replaces the legacy ``gui.py`` entry point for everyday use
while keeping existing backend logic in ``script.py``.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
from typing import Any, Callable, Dict, List, Optional, Set

from PIL import Image, ImageTk
from ttkwidgets import CheckboxTreeview
from ttkwidgets.checkboxtreeview import IM_CHECKED, IM_TRISTATE, IM_UNCHECKED

import script
import localization


DATA_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = DATA_DIR / "settings.json"
LANGUAGE_DIR = DATA_DIR / "language"
DEFAULT_SETTINGS: Dict[str, object] = {
    "remember_path": False,
    "last_path": "",
    "auto_set_999": False,
    "auto_overwrite": False,
    "source_save_path": "",
    "target_save_path": "",
    "english_ui": False,
    "language": "ko_kr",
    "highlight_locked_items": False,
    "highlight_locked_secrets": False,
}

SAVE_FILENAME_VARIANTS: tuple[str, ...] = (
    "rep_persistentgamedata",
    "rep+persistentgamedata",
    "rep+_persistentgamedata",
)

LOCKED_ITEM_TAG = "locked_highlight"
LOCKED_ITEM_BACKGROUND = "#f8d7da"
UNLOCKED_ITEM_TAG = "unlocked_highlight"
UNLOCKED_ITEM_BACKGROUND = "#e6f4ea"
LOCKED_SECRET_TAG = "secret_locked_highlight"
UNLOCKED_SECRET_TAG = "secret_unlocked_highlight"
LOCKED_SECRET_BACKGROUND = LOCKED_ITEM_BACKGROUND
UNLOCKED_SECRET_BACKGROUND = UNLOCKED_ITEM_BACKGROUND


def _strip_focus_elements(layout: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Recursively remove ttk focus elements from a layout definition."""

    cleaned: list[tuple[str, dict]] = []
    for element, options in layout:
        if "focus" in element.lower():
            if isinstance(options, dict):
                children = options.get("children")
                if isinstance(children, (list, tuple)):
                    cleaned.extend(_strip_focus_elements(list(children)))
            continue
        new_options = dict(options)
        children = new_options.get("children")
        if isinstance(children, (list, tuple)):
            new_options["children"] = _strip_focus_elements(list(children))
        cleaned.append((element, new_options))
    return cleaned


def _remove_focus_highlight(widget: tk.Misc) -> None:
    """Recursively disable Tk highlight borders and focus traversal."""

    for option, value in ("highlightthickness", 0), ("takefocus", 0):
        try:
            widget.configure(**{option: value})
        except tk.TclError:
            pass
    try:
        background = widget.cget("background")
    except tk.TclError:
        background = ""
    if background:
        for option in ("highlightbackground", "highlightcolor"):
            try:
                widget.configure(**{option: background})
            except tk.TclError:
                pass
    for child in widget.winfo_children():
        _remove_focus_highlight(child)


def _suppress_focus_indicators(root: tk.Misc) -> None:
    """Remove dotted focus outlines from common ttk widget styles."""

    try:
        default_bg = root.cget("background")
    except tk.TclError:
        default_bg = ""
    for option in (
        "*highlightthickness",
        "*FocusHighlightThickness",
    ):
        root.option_add(option, 0)
    if default_bg:
        for option in ("*highlightbackground", "*highlightcolor"):
            root.option_add(option, default_bg)

    style = ttk.Style(root)

    def _collect_style_names(widget: tk.Misc) -> set[str]:
        names: set[str] = set()
        try:
            widget_style = widget.cget("style")
        except tk.TclError:
            widget_style = ""
        if widget_style:
            names.add(str(widget_style))
        try:
            class_name = widget.winfo_class()
        except tk.TclError:
            class_name = ""
        if class_name and class_name not in {"Tk"}:
            names.add(class_name)
        for child in widget.winfo_children():
            names.update(_collect_style_names(child))
        return names

    def _expand_style_name(style_name: str) -> set[str]:
        variants: set[str] = set()
        if not style_name:
            return variants
        variants.add(style_name)
        if "." in style_name:
            prefix, suffix = style_name.split(".", 1)
            prefix_candidates = {prefix}
            suffix_candidates = {suffix}
            if prefix.startswith("T") and len(prefix) > 1:
                prefix_candidates.add(prefix[1:])
            elif prefix:
                prefix_candidates.add(f"T{prefix}")
            if suffix.startswith("T") and len(suffix) > 1:
                suffix_candidates.add(suffix[1:])
            elif suffix:
                suffix_candidates.add(f"T{suffix}")
            for pre in prefix_candidates:
                for suf in suffix_candidates:
                    if pre and suf:
                        variants.add(f"{pre}.{suf}")
        else:
            if style_name.startswith("T") and len(style_name) > 1:
                variants.add(style_name[1:])
            else:
                variants.add(f"T{style_name}")
        return {variant for variant in variants if variant}

    def _normalize_focus_color(style_name: str) -> None:
        """Force focus rings to blend into the background for ``style_name``."""

        focus_background = ""
        for option in ("background", "fieldbackground", "lightcolor", "darkcolor"):
            try:
                value = style.lookup(style_name, option)
            except tk.TclError:
                continue
            if value:
                focus_background = value
                break
        configure: dict[str, object] = {"focuswidth": 0}
        if focus_background:
            configure["focuscolor"] = focus_background
        try:
            style.configure(style_name, **configure)
        except tk.TclError:
            pass
        if focus_background:
            try:
                style.map(
                    style_name,
                    focuscolor=[("!focus", focus_background), ("focus", focus_background)],
                )
            except tk.TclError:
                pass

    base_styles = {
        "TNotebook",
        "TNotebook.Tab",
        "TButton",
        "Toolbutton",
        "TCheckbutton",
        "TRadiobutton",
        "TMenubutton",
        "TCombobox",
        "TEntry",
        "Horizontal.TScrollbar",
        "Vertical.TScrollbar",
        "Treeview",
        "Treeview.Item",
        "IconCheckboxTreeview.Treeview.Icon",
        "IconCheckboxTreeview.Treeview.Compact",
    }
    style_names: set[str] = set(base_styles)
    style_names.update(_collect_style_names(root))
    expanded_styles: set[str] = set()
    for candidate in list(style_names):
        expanded_styles.update(_expand_style_name(candidate))
    style_names.update(expanded_styles)

    processed: set[str] = set()
    for style_name in sorted(style_names):
        if not style_name or style_name in processed:
            continue
        processed.add(style_name)
        try:
            layout = style.layout(style_name)
        except tk.TclError:
            continue
        if not layout:
            continue
        try:
            style.layout(style_name, _strip_focus_elements(list(layout)))
        except tk.TclError:
            continue
        _normalize_focus_color(style_name)


def _variable_to_bool(var: Optional[tk.Variable]) -> bool:
    """Safely convert a Tkinter variable value to ``bool``."""

    if var is None:
        return False
    try:
        value = var.get()
    except tk.TclError:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)

TOTAL_COMPLETION_MARKS = 12

DEFAULT_COMPLETION_UNLOCK_MASK = getattr(script, "COMPLETION_DEFAULT_UNLOCK_MASK", 0x03)
GREED_COMPLETION_UNLOCK_MASK = getattr(script, "COMPLETION_GREED_UNLOCK_MASK", 0x0C)
COMPLETION_GREED_MARK_INDEX = 8

ITEM_UNLOCK_MASK = (
    getattr(script, "ITEM_FLAG_SEEN", 0x01)
    | getattr(script, "ITEM_FLAG_TOUCHED", 0x02)
    | getattr(script, "ITEM_FLAG_COLLECTED", 0x04)
)

MAX_ICON_HEIGHT = 32
try:
    _RESAMPLING_LANCZOS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
except AttributeError:  # Pillow < 9.1 compatibility
    _RESAMPLING_LANCZOS = Image.LANCZOS


def _load_checkbox_asset(path: str) -> Image.Image:
    with Image.open(path) as source:
        return source.convert("RGBA")


_CHECKBOX_BASE_IMAGES: Dict[str, Image.Image] = {
    "checked": _load_checkbox_asset(IM_CHECKED),
    "unchecked": _load_checkbox_asset(IM_UNCHECKED),
    "tristate": _load_checkbox_asset(IM_TRISTATE),
}


@dataclass
class SecretIcon:
    pil_image: Image.Image
    tk_image: ImageTk.PhotoImage


class IconCheckboxTreeview(CheckboxTreeview):
    """Checkbox treeview that can display custom icons alongside checkboxes."""

    _ICON_SPACING = 6
    _STYLE_BASE = "IconCheckboxTreeview.Treeview"
    _STYLE_ICON = f"{_STYLE_BASE}.Icon"
    _STYLE_COMPACT = f"{_STYLE_BASE}.Compact"
    _ICON_ROW_PADDING = 0
    _COMPACT_ROW_PADDING = 6
    _ICON_PLACEHOLDER_SIZE = (MAX_ICON_HEIGHT, MAX_ICON_HEIGHT)
    _CONFIGURED_STYLES: Set[str] = set()

    def __init__(
        self,
        master: Optional[tk.Widget] = None,
        *,
        icon_mode: bool = False,
        **kw,
    ) -> None:
        self._icon_mode = icon_mode
        if icon_mode:
            self._icon_placeholder_size = tuple(self._ICON_PLACEHOLDER_SIZE)
        else:
            self._icon_placeholder_size = (0, 0)
        self._placeholder_images: Dict[str, ImageTk.PhotoImage] = {}
        super().__init__(master, **kw)
        style = ttk.Style(master)
        checkbox_height = max(img.height for img in _CHECKBOX_BASE_IMAGES.values())
        if icon_mode:
            placeholder_height = max(self._icon_placeholder_size[1], checkbox_height)
            row_height = placeholder_height + self._ICON_ROW_PADDING
            style_name = self._STYLE_ICON
        else:
            row_height = checkbox_height + self._COMPACT_ROW_PADDING
            style_name = self._STYLE_COMPACT
        if style_name not in self._CONFIGURED_STYLES:
            base_layout = style.layout("Treeview")
            if base_layout:
                style.layout(style_name, base_layout)
            style.configure(style_name, rowheight=row_height)
            self._CONFIGURED_STYLES.add(style_name)
        self.configure(style=style_name)
        self._item_icons: Dict[str, Image.Image] = {}
        self._composite_images: Dict[str, Dict[str, ImageTk.PhotoImage]] = {}

    def set_item_icon(self, item_id: str, icon: SecretIcon) -> None:
        self._item_icons[item_id] = icon.pil_image
        if self._icon_mode:
            placeholder_width, placeholder_height = self._icon_placeholder_size
            new_width = max(placeholder_width, icon.pil_image.width)
            new_height = max(placeholder_height, icon.pil_image.height)
            if (new_width, new_height) != self._icon_placeholder_size:
                self._icon_placeholder_size = (new_width, new_height)
                self._placeholder_images.clear()
                self._refresh_placeholder_items()
        self._composite_images.pop(item_id, None)
        self._apply_item_image(item_id)

    def change_state(self, item, state):  # type: ignore[override]
        super().change_state(item, state)
        if item in self._item_icons:
            self._apply_item_image(item)

    def _apply_item_image(self, item_id: str) -> None:
        image = self._get_state_image(item_id, self._get_item_state(item_id))
        self.item(item_id, image=image)

    def _get_item_state(self, item_id: str) -> str:
        tags = self.item(item_id, "tags")
        for state in ("checked", "unchecked", "tristate"):
            if state in tags:
                return state
        return "unchecked"

    def _get_state_image(self, item_id: str, state: str) -> ImageTk.PhotoImage:
        icon_image = self._item_icons.get(item_id)
        if icon_image is None and not self._icon_mode:
            return getattr(self, f"im_{state}")
        if icon_image is None:
            return self._get_placeholder_state_image(state)
        composites = self._composite_images.setdefault(item_id, {})
        existing = composites.get(state)
        if existing is not None:
            return existing
        base = _CHECKBOX_BASE_IMAGES[state]
        composite = self._compose_images(base, icon_image)
        photo = ImageTk.PhotoImage(composite, master=self)
        composites[state] = photo
        return photo

    def _get_placeholder_state_image(self, state: str) -> ImageTk.PhotoImage:
        existing = self._placeholder_images.get(state)
        if existing is not None:
            return existing
        base = _CHECKBOX_BASE_IMAGES[state]
        composite = self._compose_images(base, None)
        photo = ImageTk.PhotoImage(composite, master=self)
        self._placeholder_images[state] = photo
        return photo

    def _compose_images(self, checkbox: Image.Image, icon: Optional[Image.Image]) -> Image.Image:
        placeholder_width, placeholder_height = self._icon_placeholder_size
        icon_width = icon.width if icon is not None else 0
        icon_height = icon.height if icon is not None else 0
        if self._icon_mode:
            icon_area_width = max(icon_width, placeholder_width)
            icon_area_height = max(icon_height, placeholder_height)
            spacing = self._ICON_SPACING if icon_area_width > 0 else 0
        else:
            icon_area_width = icon_width
            icon_area_height = icon_height
            spacing = self._ICON_SPACING if icon_area_width > 0 else 0
        width = checkbox.width + spacing + icon_area_width
        height = max(checkbox.height, icon_area_height)
        result = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        checkbox_y = (height - checkbox.height) // 2
        result.paste(checkbox, (0, checkbox_y), checkbox)
        if icon is not None:
            icon_x = checkbox.width + spacing + (icon_area_width - icon_width) // 2
            icon_y = (height - icon_height) // 2
            result.paste(icon, (icon_x, icon_y), icon)
        return result

    def _refresh_placeholder_items(self) -> None:
        if not self._icon_mode:
            return
        for item_id in self.get_children(""):
            self._refresh_placeholder_item_recursive(item_id)

    def _refresh_placeholder_item_recursive(self, item_id: str) -> None:
        if item_id not in self._item_icons:
            self._apply_item_image(item_id)
        for child in self.get_children(item_id):
            self._refresh_placeholder_item_recursive(child)


class TreeManager:
    """Manage sorting and column updates for :class:`IconCheckboxTreeview`."""

    def __init__(self, tree: IconCheckboxTreeview, records: Dict[str, Dict[str, object]]):
        self.tree = tree
        self.records = records
        self._next_direction: Dict[str, bool] = {}
        self._last_sort_column: Optional[str] = None
        self._last_sort_ascending: bool = True
        self._hidden_ids: Set[str] = set()

    def sort(self, column: str, ascending: Optional[bool] = None, update_toggle: bool = True) -> None:
        if not self.records:
            return
        if ascending is None:
            ascending = self._next_direction.get(column, True)
        entries = [
            info
            for info in self.records.values()
            if str(info.get("iid")) not in self._hidden_ids
        ]
        self._sort_entries(entries, column, ascending)
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

    def _sort_entries(self, entries: List[Dict[str, object]], column: str, ascending: bool) -> None:
        if column == "name":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            if not ascending:
                entries.reverse()
            return
        if column == "unlock":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            entries.sort(key=lambda info: 1 if info.get("unlock") else 0, reverse=not ascending)
            return
        if column == "quality":
            entries.sort(key=lambda info: str(info.get("name_sort", "")))
            entries.sort(
                key=lambda info: info.get("quality") if info.get("quality") is not None else -1,
                reverse=not ascending,
            )

    def sorted_ids(self, include_ids: Optional[Set[str]] = None) -> List[str]:
        if not self.records:
            return []
        column = self._last_sort_column or "name"
        ascending = self._last_sort_ascending if self._last_sort_column else True
        entries = list(self.records.values())
        if include_ids is None:
            include: Set[str] = {
                str(info.get("iid"))
                for info in entries
                if str(info.get("iid")) not in self._hidden_ids
            }
        else:
            include = {str(value) for value in include_ids}
            include.difference_update(self._hidden_ids)
        entries = [info for info in entries if str(info.get("iid")) in include]
        self._sort_entries(entries, column, ascending)
        return [str(info.get("iid")) for info in entries]

    def set_hidden_ids(self, hidden_ids: Set[str]) -> None:
        self._hidden_ids = {str(value) for value in hidden_ids if str(value)}

    def has_hidden_items(self) -> bool:
        return bool(self._hidden_ids)

    def get_visible_ids(self) -> List[str]:
        return self.sorted_ids()

    def set_unlock(self, iid: str, unlocked: bool) -> None:
        if iid in self.records:
            self.records[iid]["unlock"] = bool(unlocked)
            self.tree.set(iid, "unlock", "O" if unlocked else "X")


class IsaacSaveEditor(tk.Tk):
    """Main application window for the save editor."""

    SECRET_TAB_LABELS: Dict[str, tuple[str, str]] = {
        "Character": ("캐릭터", "Characters"),
        "Map": ("맵", "Maps"),
        "Boss": ("보스", "Bosses"),
        "Item": ("업적아이템", "Achievement Items"),
        "Item.Passive": ("패시브", "Passive"),
        "Item.Active": ("액티브", "Active"),
        "Other": ("기타", "Other"),
        "None": ("무효과", "No Effect"),
        "Trinket": ("장신구", "Trinkets"),
        "Pickup": ("픽업", "Pickups"),
        "Card": ("카드", "Cards"),
        "Rune": ("룬", "Runes"),
        "Pill": ("알약", "Pills"),
    }
    SECRET_FALLBACK_TYPE = "Other"
    SECRET_SEARCH_TYPES = frozenset({"Item.Passive", "Item.Active", "Trinket"})

    def _text(self, korean: str, english: str | None = None) -> str:
        english = english or korean
        korean = korean or english
        language_code = getattr(self, "_language_code", "ko_kr")
        translated = localization.translate_ui_string(
            language_code,
            english or "",
            korean or "",
        )
        if translated:
            return translated
        if localization.is_korean(language_code):
            return korean or english or ""
        if localization.is_english(language_code):
            return english or korean or ""
        return english or korean or ""

    def _register_language_binding(self, callback: Callable[[], None]) -> None:
        self._language_bindings.append(callback)
        callback()

    def _adjust_widget_width(self, widget: tk.Widget, text: str) -> None:
        if not text:
            return

        adjustable_classes: tuple[type[Any], ...] = (
            tk.Label,
            ttk.Label,
            tk.Button,
            ttk.Button,
            tk.Checkbutton,
            ttk.Checkbutton,
            ttk.Combobox,
        )

        if not isinstance(widget, adjustable_classes):
            return

        try:
            font_name = widget.cget("font") or "TkDefaultFont"
        except tk.TclError:
            font_name = "TkDefaultFont"

        try:
            font = tkfont.nametofont(font_name)
        except tk.TclError:
            font = tkfont.nametofont("TkDefaultFont")

        zero_width = max(font.measure("0"), 1)
        required_pixels = font.measure(text) + font.measure("  ")
        required_chars = max(int(math.ceil(required_pixels / zero_width)), 1)

        try:
            widget.configure(width=required_chars)
        except tk.TclError:
            pass

    def _register_text(
        self,
        widget: tk.Widget,
        korean: str,
        english: str,
        *,
        option: str = "text",
    ) -> None:
        def updater() -> None:
            translated = self._text(korean, english)
            widget.configure(**{option: translated})
            if option == "text":
                self._adjust_widget_width(widget, translated)

        self._register_language_binding(updater)

    def _register_tab_text(
        self, notebook: ttk.Notebook, tab_widget: tk.Widget, korean: str, english: str
    ) -> None:
        def updater() -> None:
            notebook.tab(tab_widget, text=self._text(korean, english))

        self._register_language_binding(updater)

    def _register_heading_text(
        self,
        tree: IconCheckboxTreeview,
        column: str,
        korean: str,
        english: str,
    ) -> None:
        def updater() -> None:
            tree.heading(column, text=self._text(korean, english))

        self._register_language_binding(updater)

    def _register_variable_text(
        self, variable: tk.StringVar, korean: str, english: str
    ) -> None:
        def updater() -> None:
            variable.set(self._text(korean, english))

        self._register_language_binding(updater)

    def _refresh_language_bindings(self) -> None:
        for callback in self._language_bindings:
            callback()

    @staticmethod
    def _normalize_sort_key(value: str) -> str:
        return " ".join((value or "").casefold().split())

    def _make_tree_item_language_updater(
        self,
        tree: IconCheckboxTreeview,
        item_id: str,
        category: str,
        translations: Dict[str, str] | None,
        *,
        is_secret: bool = True,
    ) -> Callable[[], None]:
        def updater() -> None:
            english_first = False
            if is_secret:
                english_first = self._secret_alphabetical.get(category, False)
            else:
                english_first = self._item_alphabetical.get(category, False)
            tree.item(
                item_id,
                text=self._format_display_name(translations or {}, english_first=english_first),
            )

        return updater

    def _format_display_name(
        self,
        korean_or_translations: object,
        english: str | None = None,
        *,
        english_first: bool = False,
    ) -> str:
        language_code = getattr(self, "_language_code", "ko_kr")
        translations: Dict[str, str]
        if isinstance(korean_or_translations, dict):
            translations = {
                str(key): str(value)
                for key, value in korean_or_translations.items()
                if value is not None and str(value).strip()
            }
            korean_text = translations.get("ko_kr") or translations.get("korean") or ""
            english_text = (
                translations.get("en_us")
                or translations.get("english")
                or english
                or ""
            )
        else:
            korean_text = str(korean_or_translations or "")
            english_text = str(english or "")
            translations = {
                "ko_kr": korean_text,
                "korean": korean_text,
                "en_us": english_text,
                "english": english_text,
            }

        primary_text = translations.get(language_code, "").strip()
        if not primary_text:
            if language_code == "ko_kr":
                primary_text = korean_text or english_text
            elif language_code == "en_us":
                primary_text = english_text or korean_text
            else:
                primary_text = translations.get(language_code.split("_", 1)[0], "").strip()
        if not primary_text:
            primary_text = english_text or korean_text

        secondary_text = ""
        if english_first:
            primary = english_text or primary_text
            secondary_text = primary_text if primary != primary_text else ""
        else:
            primary = primary_text
            comparison = english_text
            if language_code == "ko_kr":
                comparison = english_text
            elif language_code != "en_us":
                comparison = english_text or korean_text
            if comparison and comparison != primary:
                secondary_text = comparison

        if primary and secondary_text:
            return f"{primary} ({secondary_text})"
        return primary or secondary_text or english_text or korean_text or ""

    def _load_available_languages(self) -> Dict[str, Dict[str, str]]:
        languages: Dict[str, Dict[str, str]] = {}
        if LANGUAGE_DIR.is_dir():
            code_pattern = re.compile(r"local\s+languageCode\s*=\s*\"([^\"]+)\"")
            name_pattern = re.compile(r"languageName\s*=\s*\"([^\"]+)\"")
            for path in sorted(LANGUAGE_DIR.glob("*.lua")):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                code_match = code_pattern.search(text)
                if not code_match:
                    continue
                code = code_match.group(1).strip()
                if not code or code in languages:
                    continue
                name_match = name_pattern.search(text)
                display_name = name_match.group(1).strip() if name_match else code
                languages[code] = {"code": code, "name": display_name}
        languages.setdefault("en_us", {"code": "en_us", "name": "English"})
        languages.setdefault("ko_kr", {"code": "ko_kr", "name": "Korean"})
        return languages

    def _determine_initial_language(self) -> str:
        requested = str(self.settings.get("language") or "").strip()
        if requested in self._available_languages:
            return requested
        requested_lower = requested.lower()
        if requested_lower in self._available_languages:
            return requested_lower
        if bool(self.settings.get("english_ui", False)) and "en_us" in self._available_languages:
            return "en_us"
        if "ko_kr" in self._available_languages:
            return "ko_kr"
        if self._available_languages:
            return next(iter(sorted(self._available_languages)))
        return "en_us"

    def _prepare_language_options(
        self,
    ) -> tuple[List[str], Dict[str, str], Dict[str, str]]:
        options: List[str] = []
        display_by_code: Dict[str, str] = {}
        code_by_display: Dict[str, str] = {}
        for code in sorted(self._available_languages):
            info = self._available_languages[code]
            base_name = str(info.get("name", code)) or code
            display = self._format_language_display(code, base_name)
            if display in code_by_display:
                display = f"{display} ({code})"
            options.append(display)
            display_by_code[code] = display
            code_by_display[display] = code
        return options, display_by_code, code_by_display

    @staticmethod
    def _format_language_display(code: str, base_name: str) -> str:
        return localization.get_language_display_name(code, base_name or code)

    def _update_default_loaded_text(self) -> None:
        self._default_loaded_text = self._text(
            "불러온 파일: 없음",
            "Loaded File: None",
        )
        if hasattr(self, "loaded_file_var") and self.loaded_file_var.get() in {
            "",
            getattr(self, "_default_loaded_text", ""),
        }:
            self.loaded_file_var.set(self._default_loaded_text)

    def _apply_language_preferences(self) -> None:
        self._refresh_language_bindings()
        self._update_source_display()
        self._update_target_display()
        self._update_loaded_file_display()
        self._refresh_completion_character_options()
        self._update_completion_tree_language()
        self._update_secret_tree_language()
        self._update_item_tree_language()
        self._update_challenge_tree_language()
        self._update_language_selector()

    def _set_language(self, code: str) -> None:
        if not code or code not in self._available_languages:
            return
        if code == getattr(self, "_language_code", None):
            return
        self._language_code = code
        self._english_ui_enabled = localization.is_english(code)
        display_value = self._language_display_by_code.get(code, code)
        self._language_display_var.set(display_value)
        self.settings["language"] = code
        self.settings["english_ui"] = self._english_ui_enabled
        self._apply_language_preferences()
        self._save_settings()

    def _on_language_selection(self, event: object | None = None) -> None:
        display_value = self._language_display_var.get()
        code = self._language_code_by_display.get(display_value)
        if not code:
            normalized = display_value.strip().lower()
            for display, candidate in self._language_code_by_display.items():
                if display.lower() == normalized:
                    code = candidate
                    break
        if code:
            self._set_language(code)

    def _update_language_selector(self) -> None:
        selector = getattr(self, "_language_selector", None)
        if selector is None:
            return
        selector.configure(values=self._language_display_options)
        display_value = self._language_display_by_code.get(
            self._language_code,
            self._language_code,
        )
        self._language_display_var.set(display_value)

    def _refresh_completion_character_options(self) -> None:
        box = getattr(self, "_completion_character_box", None)
        if box is None:
            return
        options: List[str] = []
        mapping: Dict[str, int] = {}
        for info in self._completion_characters:
            display = self._format_completion_character_display(info)
            mapping[display] = int(info.get("index", 0))
            options.append(display)
        self._completion_display_to_index = mapping
        box.configure(values=options)
        if not options:
            box.configure(state="disabled")
            self._completion_character_var.set("")
            return
        box.configure(state="readonly")
        current_index = self._current_completion_char_index
        selected_display: Optional[str] = None
        if current_index is not None:
            for display, index in mapping.items():
                if index == current_index:
                    selected_display = display
                    break
        if selected_display is None:
            selected_display = options[0]
        self._completion_character_var.set(selected_display)
        self._on_completion_character_selected()

    def _update_completion_tree_language(self) -> None:
        # Completion marks do not require language-dependent display updates beyond
        # the bindings that refresh other widgets.
        pass

    def _update_secret_tree_language(self) -> None:
        for secret_type, manager in self._secret_managers.items():
            manager.sort("name", ascending=True, update_toggle=False)
            if secret_type in self.SECRET_SEARCH_TYPES:
                self._apply_secret_search_filter(secret_type)

    def _update_item_tree_language(self) -> None:
        for manager in self._item_managers.values():
            manager.sort("name", ascending=True, update_toggle=False)

    def _update_challenge_tree_language(self) -> None:
        if self._challenge_manager is not None:
            self._challenge_manager.sort("name", ascending=True, update_toggle=False)

    def _update_loaded_file_display(self) -> None:
        if not hasattr(self, "loaded_file_var"):
            return
        if self.filename:
            basename = os.path.basename(self.filename)
            self.loaded_file_var.set(
                self._text("불러온 파일", "Loaded File") + f": {basename}"
            )
        else:
            self.loaded_file_var.set(self._default_loaded_text)

    def __init__(self) -> None:
        super().__init__()
        self.title("Isaac Savefile Editor v1.0.0")

        _suppress_focus_indicators(self)

        self.filename: str = ""
        self.data: bytes | None = None

        self.settings_path = SETTINGS_PATH
        self.settings = self._load_settings()
        self._available_languages = self._load_available_languages()
        self._language_code = self._determine_initial_language()
        self._english_ui_enabled = localization.is_english(self._language_code)
        (
            self._language_display_options,
            self._language_display_by_code,
            self._language_code_by_display,
        ) = self._prepare_language_options()
        display_value = self._language_display_by_code.get(
            self._language_code,
            self._language_code,
        )
        self._language_display_var = tk.StringVar(value=display_value)
        self._language_bindings: List[Callable[[], None]] = []
        self._highlight_locked_items_var = tk.BooleanVar(
            value=bool(self.settings.get("highlight_locked_items", False))
        )
        self._highlight_locked_secrets_var = tk.BooleanVar(
            value=bool(self.settings.get("highlight_locked_secrets", False))
        )
        self.settings["language"] = self._language_code
        self.settings["english_ui"] = self._english_ui_enabled

        self._auto_set_999_default = bool(self.settings.get("auto_set_999", False))
        self._auto_overwrite_default = bool(self.settings.get("auto_overwrite", False))
        self._auto_overwrite_executed = False
        self.source_save_path = self._normalize_save_path(self.settings.get("source_save_path"))
        self.target_save_path = self._normalize_save_path(self.settings.get("target_save_path"))
        self.settings["source_save_path"] = self.source_save_path
        self.settings["target_save_path"] = self.target_save_path
        remember_path = bool(self.settings.get("remember_path", False))
        self.remember_path_var = tk.BooleanVar(value=remember_path)
        self._register_language_binding(lambda: self._update_default_loaded_text())

        self._numeric_config: Dict[str, Dict[str, object]] = {
            "donation": {
                "offset": 0x4C,
                "title": ("기부 기계", "Donation Machine"),
                "description": ("기부 기계", "Donation Machine"),
                "num_bytes": 4,
            },
            "greed": {
                "offset": 0x1B0,
                "title": ("그리드 기계", "Greed Machine"),
                "description": ("그리드 기계", "Greed Machine"),
                "num_bytes": 4,
            },
            "streak": {
                "offset": 0x54,
                "title": ("연승", "Win Streak"),
                "description": ("연승", "Win Streak"),
                "num_bytes": 4,
            },
            "eden": {
                "offset": 0x50,
                "title": ("에덴 토큰", "Eden Tokens"),
                "description": ("에덴 토큰", "Eden Tokens"),
                "num_bytes": 2,
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
        self._completion_tree: Optional[IconCheckboxTreeview] = None
        self._completion_current_mark_ids: List[str] = []
        self._current_completion_char_index: Optional[int] = None
        self._completion_character_box: Optional[ttk.Combobox] = None

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
        self._secret_icon_store: List[SecretIcon] = []
        self._secret_icon_images_by_type: Dict[str, Dict[str, SecretIcon]] = (
            self._load_secret_icons()
        )
        self._secret_trees: Dict[str, IconCheckboxTreeview] = {}
        self._secret_managers: Dict[str, TreeManager] = {}
        self._secret_alphabetical: Dict[str, bool] = {}
        self._secret_search_vars: Dict[str, tk.StringVar] = {}
        self._secret_search_filters: Dict[str, str] = {}

        self._item_trees: Dict[str, IconCheckboxTreeview] = {}
        self._item_managers: Dict[str, TreeManager] = {}
        self._item_alphabetical: Dict[str, bool] = {}

        self._secret_to_challenges: Dict[str, Set[str]] = {}
        self._challenge_to_secrets: Dict[str, Set[str]] = {}
        self._challenge_records = self._load_challenge_records()
        self._challenge_tree: Optional[IconCheckboxTreeview] = None
        self._challenge_manager: Optional[TreeManager] = None
        self._challenge_ids: List[str] = [record["iid"] for record in self._challenge_records]

        self._build_secret_challenge_links()

        self._build_layout()
        _suppress_focus_indicators(self)
        _remove_focus_highlight(self)
        self.refresh_current_values()
        self._set_initial_window_size()
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
            hyphen_to_space = normalized.replace("-", " ")
            if hyphen_to_space.strip():
                candidates.add(" ".join(hyphen_to_space.split()))
            hyphen_removed = normalized.replace("-", "")
            if hyphen_removed.strip():
                candidates.add(hyphen_removed)
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

    def _completion_mask_for_mark(self, mark_index: int) -> int:
        if mark_index == COMPLETION_GREED_MARK_INDEX:
            return GREED_COMPLETION_UNLOCK_MASK
        return DEFAULT_COMPLETION_UNLOCK_MASK

    @staticmethod
    def _normalize_save_path(value: object) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return os.path.abspath(normalized)
        return ""

    @staticmethod
    def _paths_equal(first: str, second: str) -> bool:
        if not first or not second:
            return False
        try:
            return os.path.samefile(first, second)
        except OSError:
            return os.path.abspath(first) == os.path.abspath(second)

    @staticmethod
    def _path_contains_steam(path: str) -> bool:
        normalized = path.replace("\\", "/").casefold()
        return "steam" in normalized

    def _format_selected_path(self, path: str) -> str:
        if not path:
            return self._text("선택된 파일: 없음", "Selected File: None")
        formatted = os.path.normpath(path)
        return self._text(
            f"선택된 파일: {formatted}",
            f"Selected File: {formatted}",
        )
    # ------------------------------------------------------------------
    # Layout construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.notebook = notebook

        main_tab = ttk.Frame(notebook, padding=12)
        main_tab.columnconfigure(0, weight=1)
        notebook.add(main_tab)
        self._register_tab_text(notebook, main_tab, "메인", "Main")
        self._build_main_tab(main_tab)

        completion_tab = ttk.Frame(notebook, padding=12)
        completion_tab.columnconfigure(0, weight=1)
        completion_tab.rowconfigure(2, weight=1)
        self._build_completion_tab(completion_tab)
        self._completion_tab_frame = completion_tab

        def add_secret_tab(secret_type: str) -> None:
            tab_label = self._secret_tab_labels.get(
                secret_type, (secret_type, secret_type)
            )
            secrets_tab = ttk.Frame(notebook, padding=12)
            secrets_tab.columnconfigure(0, weight=1)
            notebook.add(secrets_tab)
            self._register_tab_text(notebook, secrets_tab, tab_label[0], tab_label[1])
            self._build_secrets_tab(secrets_tab, secret_type)

        secret_order = [
            secret_type
            for secret_type in self._secret_tab_order
            if self._secret_ids_by_type.get(secret_type)
        ]
        boss_tab_type: Optional[str] = None
        none_tab_type: Optional[str] = None
        for secret_type in secret_order:
            if secret_type == "None" and none_tab_type is None:
                none_tab_type = secret_type
                continue
            if secret_type == "Boss" and boss_tab_type is None:
                boss_tab_type = secret_type
                continue
            add_secret_tab(secret_type)
        if boss_tab_type:
            add_secret_tab(boss_tab_type)

        notebook.add(completion_tab)
        self._register_tab_text(notebook, completion_tab, "체크리스트", "Checklist")

        if none_tab_type:
            add_secret_tab(none_tab_type)

    def _set_initial_window_size(self) -> None:
        notebook = getattr(self, "notebook", None)
        completion_tab = getattr(self, "_completion_tab_frame", None)
        if notebook is None or completion_tab is None:
            return
        current_tab = notebook.select()
        try:
            notebook.select(completion_tab)
        except tk.TclError:
            pass
        self.update_idletasks()
        notebook_width = notebook.winfo_reqwidth()
        notebook_height = notebook.winfo_reqheight()
        if current_tab:
            try:
                notebook.select(current_tab)
            except tk.TclError:
                pass
        width = notebook_width + 24
        height = notebook_height + 24
        self.geometry(f"{width}x{height}")

    def _build_main_tab(self, container: ttk.Frame) -> None:
        top_frame = ttk.Frame(container)
        top_frame.grid(column=0, row=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)

        open_button = ttk.Button(top_frame, command=self.open_save_file)
        open_button.grid(column=0, row=0, sticky="w")
        self._register_text(open_button, "아이작 세이브파일 열기", "Open Isaac Save File")

        self.loaded_file_var = tk.StringVar()
        self._update_default_loaded_text()
        loaded_file_label = ttk.Label(top_frame, textvariable=self.loaded_file_var)
        loaded_file_label.grid(column=1, row=0, sticky="w", padx=(10, 0))

        remember_check = ttk.Checkbutton(
            top_frame,
            variable=self.remember_path_var,
            command=self._on_remember_path_toggle,
        )
        remember_check.grid(column=0, row=1, columnspan=2, sticky="w", pady=(8, 0))
        self._register_text(
            remember_check,
            "세이브파일 자동 불러오기",
            "Auto Load Save File",
        )

        self.auto_set_999_var = tk.BooleanVar(value=self._auto_set_999_default)
        self.auto_overwrite_var = tk.BooleanVar(value=self._auto_overwrite_default)
        self.source_save_display_var = tk.StringVar(
            value=self._format_selected_path(self.source_save_path)
        )
        self.target_save_display_var = tk.StringVar(
            value=self._format_selected_path(self.target_save_path)
        )
        self._register_language_binding(self._update_source_display)
        self._register_language_binding(self._update_target_display)

        overwrite_frame = ttk.LabelFrame(container, padding=(12, 10))
        overwrite_frame.grid(column=0, row=1, sticky="ew", pady=(15, 0))
        overwrite_frame.columnconfigure(1, weight=1)
        self._register_text(
            overwrite_frame,
            "세이브파일 덮어쓰기",
            "Overwrite Save File",
        )

        auto_overwrite_check = ttk.Checkbutton(
            overwrite_frame,
            variable=self.auto_overwrite_var,
            command=self._on_auto_overwrite_toggle,
        )
        auto_overwrite_check.grid(column=0, row=0, sticky="w")
        self._register_text(
            auto_overwrite_check,
            "세이브파일 자동 덮어쓰기",
            "Overwrite Automatically",
        )

        help_button = ttk.Button(
            overwrite_frame,
            command=self._show_auto_overwrite_help,
        )
        help_button.grid(column=1, row=0, sticky="e")
        self._register_text(help_button, "도움말", "Help")

        source_button = ttk.Button(
            overwrite_frame,
            command=self._select_source_save_file,
        )
        source_button.grid(column=0, row=1, sticky="w", pady=(8, 0))
        self._register_text(
            source_button,
            "원본 세이브파일 열기",
            "Select Source Save File",
        )

        source_label = ttk.Label(
            overwrite_frame,
            textvariable=self.source_save_display_var,
            wraplength=420,
            justify="left",
        )
        source_label.grid(column=1, row=1, sticky="w", padx=(10, 0), pady=(8, 0))

        target_button = ttk.Button(
            overwrite_frame,
            command=self._select_target_save_file,
        )
        target_button.grid(column=0, row=2, sticky="w", pady=(8, 0))
        self._register_text(
            target_button,
            "덮어쓰기할 세이브파일 열기",
            "Select Target Save File",
        )

        target_label = ttk.Label(
            overwrite_frame,
            textvariable=self.target_save_display_var,
            wraplength=420,
            justify="left",
        )
        target_label.grid(column=1, row=2, sticky="w", padx=(10, 0), pady=(8, 0))

        overwrite_button = ttk.Button(
            overwrite_frame,
            command=self._overwrite_target_save_from_button,
        )
        overwrite_button.grid(column=0, row=3, sticky="w", pady=(8, 0))
        self._register_text(
            overwrite_button,
            "세이브파일 덮어쓰기",
            "Overwrite Save File",
        )

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
                title=config.get("title"),
                current_var=current_var,
                entry_var=entry_var,
                command=lambda field_key=key: self.apply_field(field_key, preserve_entry=True),
                is_first=index == 0,
            )

        auto_999_row = numeric_start_row + len(self._numeric_order)
        auto_999_frame = ttk.Frame(container)
        auto_999_frame.grid(column=0, row=auto_999_row, sticky="ew", pady=(12, 0))
        auto_999_frame.columnconfigure(0, weight=1)
        auto_999_frame.columnconfigure(1, weight=0)
        auto_999_frame.columnconfigure(2, weight=0)
        auto_999_frame.columnconfigure(3, weight=0)

        auto_999_check = ttk.Checkbutton(
            auto_999_frame,
            variable=self.auto_set_999_var,
            command=self._on_auto_set_999_toggle,
        )
        auto_999_check.grid(column=0, row=0, sticky="w")
        self._register_text(
            auto_999_check,
            "프로그램 시작 시 999로 설정",
            "Set to 999 on Startup",
        )

        set_999_button = ttk.Button(
            auto_999_frame,
            command=self.set_donation_greed_eden_to_max,
        )
        set_999_button.grid(column=1, row=0, sticky="e", padx=(10, 0))
        self._register_text(
            set_999_button,
            "기부/그리드 기계/에덴 토큰 999로 설정",
            "Set Donation/Greed/Eden Tokens to 999",
        )

        language_label = ttk.Label(auto_999_frame, text="Language")
        language_label.grid(column=2, row=0, sticky="e", padx=(10, 0))
        self._adjust_widget_width(language_label, "Language")

        language_box = ttk.Combobox(
            auto_999_frame,
            state="readonly",
            textvariable=self._language_display_var,
        )
        language_box.grid(column=3, row=0, sticky="e", padx=(6, 0))
        language_box.bind("<<ComboboxSelected>>", self._on_language_selection)
        self._language_selector = language_box
        self._update_language_selector()

        bestiary_button = ttk.Button(
            auto_999_frame,
            command=self.set_bestiary_encounters_to_one,
        )
        bestiary_button.grid(column=0, row=1, columnspan=2, sticky="w", pady=(10, 0))
        self._register_text(
            bestiary_button,
            "베스티어리 조우 수 1로 설정",
            "Set Bestiary Encounters to 1",
        )

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

        character_label = ttk.Label(header)
        character_label.pack(side="left")
        self._register_text(character_label, "캐릭터:", "Character:")

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
        self._completion_character_box = character_box

        info_label = ttk.Label(container)
        info_label.grid(column=0, row=1, sticky="w", pady=(10, 0))
        self._register_text(
            info_label,
            "체크박스를 클릭하면 즉시 저장됩니다.",
            "Changes are saved immediately when you click the checkboxes.",
        )

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
            command=self._unlock_all_completion_marks_all_characters,
        )
        unlock_all_button.grid(column=0, row=3, sticky="e", pady=(12, 0))
        self._register_text(
            unlock_all_button,
            "모든 캐릭터 체크리스트 완료",
            "Complete All Character Checklists",
        )

        if character_options:
            character_box.current(0)
            self._on_completion_character_selected()
        else:
            character_box.configure(state="disabled")
            if self._completion_tree is not None:
                self._completion_tree.state(("disabled",))

    def _format_completion_character_display(self, info: Dict[str, object]) -> str:
        translations = {
            "ko_kr": str(info.get("korean", "")).strip(),
            "en_us": str(info.get("english", "")).strip(),
        }
        extra = info.get("translations")
        if isinstance(extra, dict):
            for key, value in extra.items():
                if value:
                    translations[str(key)] = str(value)
        display = self._format_display_name(translations)
        if display:
            return display
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

        buttons: list[tuple[ttk.Button, tuple[str, str]]] = []

        select_all_button = ttk.Button(
            button_frame,
            command=lambda t=secret_type: self._select_all_secrets(t),
        )
        buttons.append((select_all_button, ("모두 선택", "Select All")))

        select_none_button = ttk.Button(
            button_frame,
            command=lambda t=secret_type: self._select_none_secrets(t),
        )
        buttons.append((select_none_button, ("모두 해제", "Select None")))

        unlock_button = ttk.Button(
            button_frame,
            command=lambda t=secret_type: self._unlock_selected_secrets(t),
        )
        buttons.append((unlock_button, ("선택 해금", "Unlock Selected")))

        lock_button = ttk.Button(
            button_frame,
            command=lambda t=secret_type: self._lock_selected_secrets(t),
        )
        buttons.append((lock_button, ("선택 미해금", "Lock Selected")))

        alpha_button = ttk.Button(
            button_frame,
            command=lambda t=secret_type: self._toggle_secret_alphabetical(t),
        )
        buttons.append((alpha_button, ("알파벳순 정렬", "Sort Alphabetically")))

        for index, (button, texts) in enumerate(buttons):
            button.grid(column=index, row=0, padx=(0 if index == 0 else 6, 0))
            self._register_text(button, *texts)

        spacer_column = len(buttons)
        button_frame.columnconfigure(spacer_column, weight=1)
        highlight_check = ttk.Checkbutton(
            button_frame,
            variable=self._highlight_locked_secrets_var,
            command=self._on_highlight_locked_secrets_toggle,
        )
        highlight_column = spacer_column + 1
        highlight_check.grid(column=highlight_column, row=0, sticky="e", padx=(12, 0))
        self._register_text(
            highlight_check,
            "해금 강조",
            "Highlight Unlock Status",
        )

        if secret_type in self.SECRET_SEARCH_TYPES:
            existing_query = self._secret_search_filters.get(secret_type, "")
            search_var = self._secret_search_vars.get(secret_type)
            if search_var is None:
                search_var = tk.StringVar(value=existing_query)
                self._secret_search_vars[secret_type] = search_var
            else:
                search_var.set(existing_query)
            entry_column = highlight_column + 1
            button_frame.columnconfigure(entry_column, weight=1)
            search_entry = ttk.Entry(
                button_frame,
                textvariable=search_var,
                width=24,
            )
            search_entry.grid(column=entry_column, row=0, sticky="ew", padx=(6, 0))
            search_entry.bind(
                "<Return>",
                lambda _event, t=secret_type: self._on_secret_search(t),
            )
            search_button = ttk.Button(
                button_frame,
                command=lambda t=secret_type: self._on_secret_search(t),
            )
            search_button.grid(column=entry_column + 1, row=0, sticky="e", padx=(6, 0))
            self._register_text(search_button, "검색", "Search")
            reset_button = ttk.Button(
                button_frame,
                command=lambda t=secret_type: self._reset_secret_search(t),
            )
            reset_button.grid(column=entry_column + 2, row=0, sticky="e", padx=(6, 0))
            self._register_text(reset_button, "초기화", "Reset")

        include_quality = secret_type.startswith("Item.")

        tree_row = 1
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
        icon_mode = secret_type in {"Item.Passive", "Item.Active", "Trinket"}
        tree = self._create_tree(tree_container, columns, icon_mode=icon_mode)
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)
        if include_quality:
            tree.column("quality", anchor="center", width=120, stretch=False)
        tree.tag_configure(LOCKED_SECRET_TAG, background=LOCKED_SECRET_BACKGROUND)

        manager = TreeManager(tree, {})
        tree.heading("#0", command=lambda m=manager: m.sort("name"))
        self._register_heading_text(tree, "#0", "이름", "Name")
        tree.heading("unlock", command=lambda m=manager: m.sort("unlock"))
        self._register_heading_text(tree, "unlock", "해금 여부", "Unlock Status")
        if include_quality:
            tree.heading("quality", command=lambda m=manager: m.sort("quality"))
            self._register_heading_text(tree, "quality", "등급", "Quality")

        records: Dict[str, Dict[str, object]] = {}
        english_first = self._secret_alphabetical.get(secret_type, False)
        for record in self._secret_records_by_type.get(secret_type, []):
            quality_value = record.get("quality")
            values: List[str] = ["X"]
            if include_quality:
                quality_display = "-" if quality_value is None else str(quality_value)
                values.append(quality_display)
            item_id = record["iid"]
            translations = dict(record.get("translations", {}))
            translations.setdefault("ko_kr", str(record.get("korean", "")))
            translations.setdefault("en_us", str(record.get("english", "")))
            display_text = self._format_display_name(
                translations,
                english_first=english_first,
            )
            icon = self._get_secret_icon(
                secret_type,
                str(record.get("unlock_name") or ""),
                str(record.get("secret_name") or ""),
                str(record.get("english") or ""),
            )
            insert_kwargs = {
                "iid": item_id,
                "text": display_text,
                "values": tuple(values),
            }
            tree.insert("", "end", **insert_kwargs)
            if icon is not None:
                tree.set_item_icon(item_id, icon)
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record.get("sort_default", record.get("name_sort")),
                "unlock": False,
                "quality": quality_value if include_quality else None,
                "sort_default": record.get("sort_default", record.get("name_sort")),
                "sort_english": record.get("sort_english", record.get("name_sort")),
            }
            self._register_language_binding(
                self._make_tree_item_language_updater(
                    tree,
                    item_id,
                    secret_type,
                    translations,
                )
            )
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._secret_trees[secret_type] = tree
        self._secret_managers[secret_type] = manager
        self._secret_alphabetical.setdefault(secret_type, False)
        if secret_type in self.SECRET_SEARCH_TYPES:
            self._apply_secret_search_filter(secret_type, update_var=True)
        self._update_secret_highlighting()

    def _build_item_tab(self, container: ttk.Frame, item_type: str) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")

        buttons: list[tuple[ttk.Button, tuple[str, str]]] = []

        select_all_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._select_all_items(t),
        )
        buttons.append((select_all_button, ("모두 선택", "Select All")))

        select_none_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._select_none_items(t),
        )
        buttons.append((select_none_button, ("모두 해제", "Select None")))

        unlock_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._unlock_selected_items(t),
        )
        buttons.append((unlock_button, ("선택 해금", "Unlock Selected")))

        mark_seen_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._mark_selected_items_seen(t),
        )
        buttons.append((mark_seen_button, ("선택 본 것으로 표시", "Mark Selected Seen")))

        lock_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._lock_selected_items(t),
        )
        buttons.append((lock_button, ("선택 미해금", "Lock Selected")))

        alpha_button = ttk.Button(
            button_frame,
            command=lambda t=item_type: self._toggle_item_alphabetical(t),
        )
        buttons.append((alpha_button, ("알파벳순 정렬", "Sort Alphabetically")))

        for index, (button, texts) in enumerate(buttons):
            button.grid(column=index, row=0, padx=(0 if index == 0 else 6, 0))
            self._register_text(button, *texts)

        button_frame.columnconfigure(len(buttons), weight=1)
        highlight_check = ttk.Checkbutton(
            button_frame,
            variable=self._highlight_locked_items_var,
            command=self._on_highlight_locked_items_toggle,
        )
        highlight_check.grid(column=len(buttons), row=0, sticky="e", padx=(12, 0))
        self._register_text(
            highlight_check,
            "해금 강조",
            "Highlight Unlock Status",
        )

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=1, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        icon_mode = item_type in {"Passive", "Active"}
        tree = self._create_tree(tree_container, ("unlock", "quality"), icon_mode=icon_mode)
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)
        tree.column("quality", anchor="center", width=120, stretch=False)
        tree.tag_configure(LOCKED_ITEM_TAG, background=LOCKED_ITEM_BACKGROUND)

        manager = TreeManager(tree, {})
        tree.heading("#0", command=lambda m=manager: m.sort("name"))
        self._register_heading_text(tree, "#0", "이름", "Name")
        tree.heading("unlock", command=lambda m=manager: m.sort("unlock"))
        self._register_heading_text(tree, "unlock", "해금 여부", "Unlock Status")
        tree.heading("quality", command=lambda m=manager: m.sort("quality"))
        self._register_heading_text(tree, "quality", "등급", "Quality")

        records: Dict[str, Dict[str, object]] = {}
        english_first = self._item_alphabetical.get(item_type, False)
        for item_id, record in self._item_records.get(item_type, {}).items():
            quality = record.get("quality")
            quality_display = "-" if quality is None else str(quality)
            translations = dict(record.get("translations", {}))
            translations.setdefault("ko_kr", str(record.get("korean", "")))
            translations.setdefault("en_us", str(record.get("english", "")))
            display_text = self._format_display_name(
                translations,
                english_first=english_first,
            )
            tree.insert("", "end", iid=item_id, text=display_text, values=("X", quality_display))
            icon = self._get_secret_icon(
                f"Item.{item_type}",
                str(record.get("english", "")),
                str(record.get("korean", "")),
            )
            if icon is not None:
                tree.set_item_icon(item_id, icon)
            records[item_id] = {
                "iid": item_id,
                "name_sort": record.get("sort_default", record.get("name_sort")),
                "unlock": False,
                "quality": quality,
                "sort_default": record.get("sort_default", record.get("name_sort")),
                "sort_english": record.get("sort_english", record.get("name_sort")),
            }
            self._register_language_binding(
                self._make_tree_item_language_updater(
                    tree,
                    item_id,
                    item_type,
                    translations,
                    is_secret=False,
                )
            )
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._item_trees[item_type] = tree
        self._item_managers[item_type] = manager
        self._item_alphabetical.setdefault(item_type, False)
        self._update_item_highlighting()

    def _build_challenges_tab(self, container: ttk.Frame) -> None:
        button_frame = ttk.Frame(container)
        button_frame.grid(column=0, row=0, sticky="w")

        buttons: list[tuple[ttk.Button, tuple[str, str]]] = []

        select_all_button = ttk.Button(
            button_frame,
            command=self._select_all_challenges,
        )
        buttons.append((select_all_button, ("모두 선택", "Select All")))

        select_none_button = ttk.Button(
            button_frame,
            command=self._select_none_challenges,
        )
        buttons.append((select_none_button, ("모두 해제", "Select None")))

        unlock_button = ttk.Button(
            button_frame,
            command=self._unlock_selected_challenges,
        )
        buttons.append((unlock_button, ("선택 해금", "Unlock Selected")))

        unlock_all_button = ttk.Button(
            button_frame,
            command=self._unlock_all_challenges,
        )
        buttons.append((unlock_all_button, ("모두 완료", "Complete All")))

        lock_button = ttk.Button(
            button_frame,
            command=self._lock_selected_challenges,
        )
        buttons.append((lock_button, ("선택 미해금", "Lock Selected")))

        for index, (button, texts) in enumerate(buttons):
            button.grid(column=index, row=0, padx=(0 if index == 0 else 6, 0))
            self._register_text(button, *texts)

        tree_row = 1
        container.rowconfigure(tree_row, weight=1)

        tree_container = ttk.Frame(container)
        tree_container.grid(column=0, row=tree_row, sticky="nsew", pady=(12, 0))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        tree = self._create_tree(tree_container, ("unlock",))
        tree.column("#0", anchor="w", width=360, stretch=True)
        tree.column("unlock", anchor="center", width=140, stretch=False)

        manager = TreeManager(tree, {})
        tree.heading("#0", command=lambda m=manager: m.sort("name"))
        self._register_heading_text(tree, "#0", "이름", "Name")
        tree.heading("unlock", command=lambda m=manager: m.sort("unlock"))
        self._register_heading_text(tree, "unlock", "해금 여부", "Unlock Status")

        records: Dict[str, Dict[str, object]] = {}
        for record in self._challenge_records:
            item_id = record["iid"]
            translations = {
                "ko_kr": str(record.get("korean", "")),
                "en_us": str(record.get("english", "")),
            }
            extra = record.get("translations")
            if isinstance(extra, dict):
                translations.update({str(k): str(v) for k, v in extra.items() if v})
            display_text = self._format_display_name(translations)
            tree.insert("", "end", iid=item_id, text=display_text, values=("X",))
            records[record["iid"]] = {
                "iid": record["iid"],
                "name_sort": record.get("sort_default", record.get("name_sort")),
                "unlock": False,
                "quality": None,
                "sort_default": record.get("sort_default", record.get("name_sort")),
                "sort_english": record.get("sort_english", record.get("name_sort")),
            }
            self._register_language_binding(
                self._make_tree_item_language_updater(
                    tree,
                    item_id,
                    "challenge",
                    translations,
                    is_secret=False,
                )
            )
        manager.records = records
        manager.sort("name", ascending=True, update_toggle=False)

        self._challenge_tree = tree
        self._challenge_manager = manager

    def _create_completion_tree(self, container: ttk.Frame) -> IconCheckboxTreeview:
        tree = IconCheckboxTreeview(container, columns=(), show="tree", selectmode="none")
        tree.grid(column=0, row=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        yscroll.grid(column=1, row=0, sticky="ns")
        tree.configure(yscrollcommand=yscroll.set)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        xscroll.grid(column=0, row=1, sticky="ew")
        tree.configure(xscrollcommand=xscroll.set)
        return tree

    def _create_tree(
        self,
        container: ttk.Frame,
        columns: tuple[str, ...],
        *,
        icon_mode: bool = False,
    ) -> IconCheckboxTreeview:
        tree = IconCheckboxTreeview(
            container,
            columns=columns,
            show="tree headings",
            selectmode="none",
            icon_mode=icon_mode,
        )
        tree.grid(column=0, row=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        yscroll.grid(column=1, row=0, sticky="ns")
        tree.configure(yscrollcommand=yscroll.set)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        xscroll.grid(column=0, row=1, sticky="ew")
        tree.configure(xscrollcommand=xscroll.set)
        return tree

    def _lock_tree(self, tree: IconCheckboxTreeview) -> None:
        self._locked_tree_ids.add(id(tree))

    def _unlock_tree(self, tree: IconCheckboxTreeview) -> None:
        self._locked_tree_ids.discard(id(tree))

    def _is_tree_locked(self, tree: IconCheckboxTreeview) -> bool:
        return id(tree) in self._locked_tree_ids

    def _get_checked_or_warn(self, tree: IconCheckboxTreeview) -> Set[str] | None:
        selected = set(tree.get_checked())
        if not selected:
            messagebox.showinfo(
                self._text("선택 없음", "No Selection"),
                self._text("먼저 체크박스에서 항목을 선택해주세요.", "Please select at least one entry."),
            )
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
        tab_labels: Dict[str, tuple[str, str]] = {}
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
                tab_labels[secret_type] = self.SECRET_TAB_LABELS.get(
                    secret_type, (secret_type, secret_type)
                )
                type_order.append(secret_type)

        map_duplicate_secret_ids = {"57", "78"}
        with csv_path.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []
            base_columns = {
                "SecretID",
                "SecretName",
                "UnlockName",
                "Type",
                "Korean",
                "UnlockedFlag",
            }
            language_columns = [
                name
                for name in fieldnames
                if name not in base_columns and name is not None
            ]
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
                if secret_type_raw in {"Item", "Pill"}:
                    english_name = unlock_name or secret_name
                else:
                    english_name = secret_name or unlock_name
                korean_name = korean
                translations: Dict[str, str] = {
                    "ko_kr": korean_name,
                    "en_us": english_name,
                }
                for column in language_columns:
                    value = (row.get(column) or "").strip()
                    if value:
                        translations[column] = value
                display = self._format_display_name(translations)
                primary_name = korean_name or english_name or secret_id
                record = {
                    "iid": secret_id,
                    "display": display,
                    "name_sort": self._normalize_sort_key(primary_name),
                    "quality": quality_value,
                    "unlock_name": unlock_name,
                    "secret_name": secret_name,
                    "korean": korean,
                    "english": english_name,
                    "translations": translations,
                    "sort_default": self._normalize_sort_key(korean_name or english_name or secret_id),
                    "sort_english": self._normalize_sort_key(english_name or korean_name or secret_id),
                }
                records_by_type[secret_type].append(record)
                ids_by_type[secret_type].append(secret_id)
                details_by_id[secret_id] = {
                    "unlock_name": unlock_name,
                    "secret_name": secret_name,
                    "korean": korean,
                    "display": display,
                    "translations": translations,
                    "secret_type": secret_type,
                }
                if secret_type == "Item.Passive" and secret_id in map_duplicate_secret_ids:
                    register_type("Map")
                    records_by_type["Map"].append(record.copy())
                    ids_by_type["Map"].append(secret_id)
        if "Pickup" in type_order:
            type_order.remove("Pickup")
            if "Pill" in type_order:
                pill_index = type_order.index("Pill")
                type_order.insert(pill_index + 1, "Pickup")
            elif "None" in type_order:
                type_order.insert(type_order.index("None"), "Pickup")
            else:
                type_order.append("Pickup")
        if "None" in type_order:
            type_order = [
                secret_type
                for secret_type in type_order
                if secret_type != "None"
            ]
            type_order.append("None")
        return records_by_type, ids_by_type, tab_labels, type_order, details_by_id

    def _load_secret_icons(self) -> Dict[str, Dict[str, SecretIcon]]:
        icons_by_type: Dict[str, Dict[str, SecretIcon]] = {
            "Item.Passive": {},
            "Item.Active": {},
            "Trinket": {},
        }
        icon_root = DATA_DIR / "icons"
        icon_sets = [
            (icon_root / "items", ("Item.Passive", "Item.Active")),
            (icon_root / "trinkets", ("Trinket",)),
        ]
        for folder, secret_types in icon_sets:
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.png")):
                try:
                    with Image.open(path) as source:
                        image = source.convert("RGBA")
                except (OSError, ValueError):
                    continue
                if image.height > MAX_ICON_HEIGHT and image.height > 0:
                    ratio = MAX_ICON_HEIGHT / float(image.height)
                    new_width = max(1, int(round(image.width * ratio)))
                    image = image.resize((new_width, MAX_ICON_HEIGHT), _RESAMPLING_LANCZOS)
                tk_image = ImageTk.PhotoImage(image)
                icon_asset = SecretIcon(pil_image=image, tk_image=tk_image)
                self._secret_icon_store.append(icon_asset)
                base_name = path.stem
                if "__" in base_name:
                    prefix, _ = base_name.rsplit("__", 1)
                    if prefix:
                        base_name = prefix
                if "___" in base_name:
                    base_name = base_name.replace("___", "???")
                base_name = re.sub(r"^(Collectible|Trinket)_", "", base_name)
                base_name = re.sub(r"_icon$", "", base_name)
                base_name = re.sub(r"[_-]+", " ", base_name).strip()
                base_name = re.sub(r"\b(item|trinket)\b$", "", base_name, flags=re.IGNORECASE).strip()
                lookup_keys = self._build_lookup_keys(base_name)
                if not lookup_keys:
                    continue
                for secret_type in secret_types:
                    mapping = icons_by_type.setdefault(secret_type, {})
                    for key in lookup_keys:
                        mapping.setdefault(key, icon_asset)
        return icons_by_type

    def _get_secret_icon(self, secret_type: str, *names: str) -> Optional[SecretIcon]:
        mapping = self._secret_icon_images_by_type.get(secret_type)
        if not mapping:
            return None
        for name in names:
            if not name:
                continue
            for key in self._build_lookup_keys(name):
                icon = mapping.get(key)
                if icon is not None:
                    return icon
        return None

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
                translations = {"ko_kr": korean, "en_us": english}
                display = self._format_display_name(translations)
                record = {
                    "iid": item_id,
                    "display": display,
                    "name_sort": self._normalize_sort_key(korean or english or item_id),
                    "quality": quality_value,
                    "english": english,
                    "korean": korean,
                    "item_type": item_type,
                    "translations": translations,
                    "sort_default": self._normalize_sort_key(korean or english or item_id),
                    "sort_english": self._normalize_sort_key(english or korean or item_id),
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
                translations = {"ko_kr": korean, "en_us": challenge_name}
                display = self._format_display_name(translations)
                records.append(
                    {
                        "iid": challenge_id,
                        "display": display,
                        "name_sort": self._normalize_sort_key(
                            korean or challenge_name or challenge_id
                        ),
                        "english": challenge_name,
                        "korean": korean,
                        "translations": translations,
                        "sort_default": self._normalize_sort_key(
                            korean or challenge_name or challenge_id
                        ),
                        "sort_english": self._normalize_sort_key(
                            challenge_name or korean or challenge_id
                        ),
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
        try:
            current_values = script.getChecklistUnlocks(self.data, self._current_completion_char_index)
        except Exception:
            current_values = []
        mark_count = max(
            TOTAL_COMPLETION_MARKS,
            len(current_values),
            len(self._completion_current_mark_ids),
        )
        new_values: List[int] = list(current_values) + [0] * max(0, mark_count - len(current_values))
        for mark_id in self._completion_current_mark_ids:
            try:
                index = int(mark_id)
            except (TypeError, ValueError):
                continue
            if index >= len(new_values):
                new_values.extend([0] * (index + 1 - len(new_values)))
            checked = tree.tag_has("checked", mark_id)
            mask = self._completion_mask_for_mark(index)
            current = new_values[index]
            if checked:
                updated = current | mask
            else:
                updated = current & ~mask
            new_values[index] = updated
        success = self._apply_update(
            lambda data, idx=self._current_completion_char_index, values=new_values: script.updateCheckListUnlocks(
                data, idx, values
            ),
            self._text(
                "체크리스트를 업데이트하지 못했습니다.",
                "Failed to update checklists.",
            ),
        )
        if not success:
            self._refresh_completion_tab()

    def _unlock_all_completion_marks_all_characters(self) -> None:
        if not self._ensure_data_loaded():
            return
        proceed = messagebox.askyesno(
            self._text("체크리스트 완료", "Complete Checklists"),
            self._text(
                "모든 캐릭터의 체크리스트를 완료하시겠습니까?",
                "Complete every character checklist?",
            ),
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
            messagebox.showwarning(
                self._text("체크리스트 완료", "Complete Checklists"),
                self._text("완료할 캐릭터 정보를 찾을 수 없습니다.", "No character data available to complete."),
            )
            return
        mark_count = max(
            (len(marks) for marks in self._completion_marks_by_character.values()),
            default=TOTAL_COMPLETION_MARKS,
        )
        if mark_count <= 0:
            mark_count = TOTAL_COMPLETION_MARKS

        def updater(data: bytes) -> bytes:
            result = data
            for index in char_indices:
                try:
                    current_values = script.getChecklistUnlocks(result, index)
                except Exception:
                    current_values = []
                target_length = max(mark_count, len(current_values), TOTAL_COMPLETION_MARKS)
                values = list(current_values) + [0] * max(0, target_length - len(current_values))
                for mark_index in range(target_length):
                    mask = self._completion_mask_for_mark(mark_index)
                    values[mark_index] = values[mark_index] | mask
                result = script.updateCheckListUnlocks(result, index, values)
            return result

        if self._apply_update(
            updater,
            self._text(
                "모든 캐릭터 체크리스트를 완료하지 못했습니다.",
                "Failed to complete all character checklists.",
            ),
        ):
            messagebox.showinfo(
                self._text("완료", "Done"),
                self._text("모든 캐릭터 체크리스트를 완료했습니다.", "All character checklists are complete."),
            )

    def _select_all_secrets(self, secret_type: str) -> None:
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            if manager is not None:
                target_ids = manager.get_visible_ids()
            else:
                target_ids = self._secret_ids_by_type.get(secret_type, [])
            for secret_id in target_ids:
                tree.change_state(secret_id, "checked")
        finally:
            self._unlock_tree(tree)

    def _select_none_secrets(self, secret_type: str) -> None:
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None:
            return
        self._lock_tree(tree)
        try:
            if manager is not None:
                target_ids = manager.get_visible_ids()
            else:
                target_ids = self._secret_ids_by_type.get(secret_type, [])
            for secret_id in target_ids:
                tree.change_state(secret_id, "unchecked")
        finally:
            self._unlock_tree(tree)

    def _toggle_secret_alphabetical(self, secret_type: str) -> None:
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None or manager is None:
            return
        new_state = not self._secret_alphabetical.get(secret_type, False)
        self._secret_alphabetical[secret_type] = new_state
        records = self._secret_records_by_type.get(secret_type, [])
        for record in records:
            item_id = record.get("iid")
            if not item_id:
                continue
            manager_record = manager.records.get(item_id)
            if manager_record:
                key = "sort_english" if new_state else "sort_default"
                if key in manager_record:
                    manager_record["name_sort"] = manager_record.get(key, manager_record.get("name_sort"))
            tree.item(
                item_id,
                text=self._format_display_name(
                    record.get("translations", {}),
                    english_first=new_state,
                ),
            )
        manager.sort("name", ascending=True, update_toggle=False)
        tree.yview_moveto(0)

    def _on_secret_search(self, secret_type: str) -> None:
        if secret_type not in self.SECRET_SEARCH_TYPES:
            return
        var = self._secret_search_vars.get(secret_type)
        query = var.get() if var is not None else self._secret_search_filters.get(secret_type, "")
        self._apply_secret_search_filter(secret_type, query)

    def _reset_secret_search(self, secret_type: str) -> None:
        if secret_type not in self.SECRET_SEARCH_TYPES:
            return
        self._apply_secret_search_filter(secret_type, "", update_var=True)

    def _apply_secret_search_filter(
        self,
        secret_type: str,
        query: Optional[str] = None,
        *,
        update_var: bool = False,
    ) -> None:
        if secret_type not in self.SECRET_SEARCH_TYPES:
            return
        var = self._secret_search_vars.get(secret_type)
        if query is None:
            if var is not None:
                raw_query = var.get()
            else:
                raw_query = self._secret_search_filters.get(secret_type, "")
        else:
            raw_query = query
        raw_query = str(raw_query or "")
        if update_var and var is not None:
            var.set(raw_query)
        normalized = self._normalize_search_text(raw_query)
        manager = self._secret_managers.get(secret_type)
        tree = self._secret_trees.get(secret_type)
        if not normalized:
            self._secret_search_filters.pop(secret_type, None)
            if manager is not None and manager.has_hidden_items() and tree is not None:
                self._filter_secret_tree(secret_type, None)
            return
        self._secret_search_filters[secret_type] = raw_query
        if manager is None or tree is None:
            return
        language_code = getattr(self, "_language_code", "ko_kr")
        allowed_ids: Set[str] = set()
        for record in self._secret_records_by_type.get(secret_type, []):
            item_id = str(record.get("iid") or "").strip()
            if not item_id:
                continue
            translations = dict(record.get("translations", {}))
            english_value = str(translations.get("en_us") or record.get("english") or "")
            if language_code == "en_us":
                local_value = english_value
            else:
                local_value = str(translations.get(language_code) or "")
                if not local_value:
                    if localization.is_korean(language_code):
                        local_value = str(translations.get("ko_kr") or record.get("korean") or "")
                    if not local_value:
                        local_value = english_value
            candidates = []
            if english_value:
                candidates.append(english_value)
            if local_value and local_value not in candidates:
                candidates.append(local_value)
            for candidate in candidates:
                normalized_candidate = self._normalize_search_text(candidate)
                if normalized_candidate and normalized in normalized_candidate:
                    allowed_ids.add(item_id)
                    break
        self._filter_secret_tree(secret_type, allowed_ids)

    def _filter_secret_tree(
        self, secret_type: str, allowed_ids: Optional[Set[str]]
    ) -> None:
        tree = self._secret_trees.get(secret_type)
        manager = self._secret_managers.get(secret_type)
        if tree is None or manager is None:
            return
        all_ids = [str(secret_id) for secret_id in self._secret_ids_by_type.get(secret_type, [])]
        all_ids_set = set(all_ids)
        if allowed_ids is None:
            manager.set_hidden_ids(set())
            order = manager.sorted_ids()
        else:
            allowed_set = {str(value) for value in allowed_ids if str(value)}
            manager.set_hidden_ids(all_ids_set - allowed_set)
            order = manager.sorted_ids(include_ids=allowed_set)
        for secret_id in all_ids:
            tree.detach(secret_id)
        for secret_id in order:
            tree.reattach(secret_id, "", "end")
        tree.yview_moveto(0)
        highlight_enabled = _variable_to_bool(self._highlight_locked_secrets_var)
        for secret_id, info in manager.records.items():
            self._apply_secret_highlight(
                tree,
                secret_id,
                bool(info.get("unlock")),
                enabled=highlight_enabled,
            )

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", "", value).casefold()

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

        self._apply_update(
            updater,
            self._text("비밀을 업데이트하지 못했습니다.", "Failed to update secrets."),
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

        self._apply_update(
            updater,
            self._text("비밀을 업데이트하지 못했습니다.", "Failed to update secrets."),
        )

    def _collect_unlocked_secrets(self) -> Set[str]:
        unlocked: Set[str] = set()
        for manager in self._secret_managers.values():
            for secret_id, info in manager.records.items():
                if info.get("unlock"):
                    unlocked.add(secret_id)
        return unlocked

    def _apply_secret_highlight(
        self,
        tree: IconCheckboxTreeview,
        secret_id: str,
        unlocked: bool,
        *,
        enabled: Optional[bool] = None,
    ) -> None:
        if enabled is None:
            enabled = _variable_to_bool(self._highlight_locked_secrets_var)
        tags = set(tree.item(secret_id, "tags"))
        if enabled:
            if unlocked:
                tags.discard(LOCKED_SECRET_TAG)
                tags.add(UNLOCKED_SECRET_TAG)
            else:
                tags.discard(UNLOCKED_SECRET_TAG)
                tags.add(LOCKED_SECRET_TAG)
        else:
            tags.discard(LOCKED_SECRET_TAG)
            tags.discard(UNLOCKED_SECRET_TAG)
        tree.item(secret_id, tags=tuple(tags))

    def _update_secret_highlighting(self) -> None:
        enabled = _variable_to_bool(self._highlight_locked_secrets_var)
        for secret_type, tree in self._secret_trees.items():
            tree.tag_configure(LOCKED_SECRET_TAG, background=LOCKED_SECRET_BACKGROUND)
            tree.tag_configure(UNLOCKED_SECRET_TAG, background=UNLOCKED_SECRET_BACKGROUND)
            manager = self._secret_managers.get(secret_type)
            if manager is None:
                continue
            for secret_id, info in manager.records.items():
                self._apply_secret_highlight(
                    tree,
                    secret_id,
                    bool(info.get("unlock")),
                    enabled=enabled,
                )

    def _on_highlight_locked_secrets_toggle(self) -> None:
        enabled = _variable_to_bool(self._highlight_locked_secrets_var)
        self.settings["highlight_locked_secrets"] = enabled
        self._save_settings()
        self._update_secret_highlighting()

    def _apply_item_highlight(
        self,
        tree: IconCheckboxTreeview,
        item_id: str,
        unlocked: bool,
        *,
        enabled: Optional[bool] = None,
    ) -> None:
        if enabled is None:
            enabled = _variable_to_bool(self._highlight_locked_items_var)
        tags = set(tree.item(item_id, "tags"))
        if enabled:
            if unlocked:
                tags.discard(LOCKED_ITEM_TAG)
                tags.add(UNLOCKED_ITEM_TAG)
            else:
                tags.discard(UNLOCKED_ITEM_TAG)
                tags.add(LOCKED_ITEM_TAG)
        else:
            tags.discard(LOCKED_ITEM_TAG)
            tags.discard(UNLOCKED_ITEM_TAG)
        tree.item(item_id, tags=tuple(tags))

    def _update_item_highlighting(self) -> None:
        enabled = _variable_to_bool(self._highlight_locked_items_var)
        for item_type, tree in self._item_trees.items():
            tree.tag_configure(LOCKED_ITEM_TAG, background=LOCKED_ITEM_BACKGROUND)
            tree.tag_configure(UNLOCKED_ITEM_TAG, background=UNLOCKED_ITEM_BACKGROUND)
            manager = self._item_managers.get(item_type)
            if manager is None:
                continue
            for item_id, info in manager.records.items():
                self._apply_item_highlight(
                    tree,
                    item_id,
                    bool(info.get("unlock")),
                    enabled=enabled,
                )

    def _on_highlight_locked_items_toggle(self) -> None:
        enabled = _variable_to_bool(self._highlight_locked_items_var)
        self.settings["highlight_locked_items"] = enabled
        self._save_settings()
        self._update_item_highlighting()

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

    def _toggle_item_alphabetical(self, item_type: str) -> None:
        tree = self._item_trees.get(item_type)
        manager = self._item_managers.get(item_type)
        if tree is None or manager is None:
            return
        new_state = not self._item_alphabetical.get(item_type, False)
        self._item_alphabetical[item_type] = new_state
        for item_id, manager_record in manager.records.items():
            key = "sort_english" if new_state else "sort_default"
            if key in manager_record:
                manager_record["name_sort"] = manager_record.get(key, manager_record.get("name_sort"))
            record = self._item_records.get(item_type, {}).get(item_id, {})
            tree.item(
                item_id,
                text=self._format_display_name(
                    record.get("translations", {}),
                    english_first=new_state,
                ),
            )
        manager.sort("name", ascending=True, update_toggle=False)
        tree.yview_moveto(0)

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
            self._text("아이템을 업데이트하지 못했습니다.", "Failed to update items."),
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
            self._text("아이템을 업데이트하지 못했습니다.", "Failed to update items."),
        )

    def _mark_selected_items_seen(self, item_type: str) -> None:
        if not self._ensure_data_loaded():
            return
        tree = self._item_trees.get(item_type)
        manager = self._item_managers.get(item_type)
        if tree is None or manager is None:
            return
        selected = self._get_checked_or_warn(tree)
        if not selected:
            return
        ids_sorted = sorted(selected, key=lambda value: int(value))
        self._apply_update(
            lambda data: script.markItemsSeen(data, ids_sorted),
            self._text("아이템을 업데이트하지 못했습니다.", "Failed to update items."),
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

        self._apply_update(
            updater,
            self._text("도전과제를 업데이트하지 못했습니다.", "Failed to update challenges."),
        )

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

        self._apply_update(
            updater,
            self._text("도전과제를 업데이트하지 못했습니다.", "Failed to update challenges."),
        )

    def _unlock_all_challenges(self) -> None:
        if not self._ensure_data_loaded():
            return
        if not self._challenge_ids:
            return
        challenge_list = sorted(self._challenge_ids, key=lambda value: int(value))

        def updater(data: bytes) -> bytes:
            return script.updateChallenges(data, challenge_list)

        if self._apply_update(
            updater,
            self._text("도전과제를 업데이트하지 못했습니다.", "Failed to update challenges."),
        ):
            messagebox.showinfo(
                self._text("완료", "Done"),
                self._text("모든 도전과제를 완료했습니다.", "All challenges have been marked as complete."),
            )

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
            messagebox.showwarning(
                self._text("파일 없음", "No File"),
                self._text("먼저 세이브 파일을 열어주세요.", "Please open a save file first."),
            )
            return False
        return True

    def _apply_update(self, updater: Callable[[bytes], bytes], error_message: str) -> bool:
        if self.data is None or not self.filename:
            messagebox.showwarning(
                self._text("파일 없음", "No File"),
                self._text("먼저 세이브 파일을 열어주세요.", "Please open a save file first."),
            )
            return False
        try:
            new_data = updater(self.data)
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            messagebox.showerror(
                self._text("업데이트 실패", "Update Failed"),
                f"{error_message}\n{exc}",
            )
            return False
        updated_with_checksum = script.updateChecksum(new_data)
        try:
            with open(self.filename, "wb") as file:
                file.write(updated_with_checksum)
        except OSError as exc:
            messagebox.showerror(
                self._text("저장 실패", "Save Failed"),
                self._text("세이브 파일을 저장하지 못했습니다.", "Could not save the file.")
                + f"\n{exc}",
            )
            return False
        self.data = updated_with_checksum
        self.refresh_current_values()
        self._apply_auto_overwrite_if_enabled(prefer_loaded_file=True)
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
        unlocked_ids = {}
        for index, value in enumerate(values):
            mask = self._completion_mask_for_mark(index)
            if value & mask:
                unlocked_ids[str(index)] = True
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
        highlight_enabled = _variable_to_bool(self._highlight_locked_secrets_var)
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
                    self._apply_secret_highlight(
                        tree,
                        secret_id,
                        unlocked,
                        enabled=highlight_enabled,
                    )
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
            unlocked_ids = {
                str(index + 1)
                for index, value in enumerate(items)
                if value & ITEM_UNLOCK_MASK
            }
        highlight_enabled = _variable_to_bool(self._highlight_locked_items_var)
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
                    self._apply_item_highlight(
                        tree,
                        item_id,
                        unlocked,
                        enabled=highlight_enabled,
                    )
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
        title_ko, title_en = ("", "")
        if isinstance(title, tuple):
            title_ko, title_en = title
        elif isinstance(title, str):
            title_ko = title_en = title
        self._register_text(section, title_ko, title_en)

        current_label = ttk.Label(section)
        current_label.grid(column=0, row=0, sticky="w")
        self._register_text(current_label, "현재값:", "Current:")
        ttk.Label(section, textvariable=current_var).grid(column=1, row=0, sticky="w")

        new_value_label = ttk.Label(section)
        new_value_label.grid(column=0, row=1, sticky="w", pady=(8, 0))
        self._register_text(new_value_label, "새 값:", "New Value:")
        entry_button_frame = ttk.Frame(section)
        entry_button_frame.grid(
            column=1, row=1, columnspan=2, sticky="w", pady=(8, 0)
        )

        entry = ttk.Entry(entry_button_frame, textvariable=entry_var, width=12)
        entry.pack(side="left")

        apply_button = ttk.Button(entry_button_frame, command=command)
        apply_button.pack(side="left", padx=(6, 0))
        self._register_text(apply_button, "적용", "Apply")

    def _select_source_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title=self._text("원본 세이브파일 선택", "Select Source Save File"),
            initialdir=self._get_savefile_initial_directory(
                self.source_save_path, self.target_save_path
            ),
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return
        normalized = self._normalize_save_path(filename)
        if self.target_save_path:
            source_name = os.path.basename(normalized)
            target_name = os.path.basename(self.target_save_path)
            if source_name != target_name:
                messagebox.showerror(
                    self._text("경고", "Warning"),
                    self._text("파일 이름이 다릅니다.", "The file names do not match."),
                )
                return
        self.source_save_path = normalized
        self.settings["source_save_path"] = normalized
        self._update_source_display()
        self._save_settings()
        self._apply_auto_overwrite_if_enabled(show_message=True)

    def _select_target_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title=self._text("덮어쓰기할 세이브파일 선택", "Select Target Save File"),
            initialdir=self._get_savefile_initial_directory(
                self.target_save_path, self.source_save_path
            ),
            filetypes=(("dat files", "*.dat"), ("all files", "*.*")),
        )
        if not filename:
            return
        normalized = self._normalize_save_path(filename)
        if not self._path_contains_steam(normalized):
            proceed = messagebox.askyesno(
                self._text("경로 확인", "Confirm Path"),
                self._text(
                    "아이작 세이브파일 경로가 아닌 것 같습니다. 그래도 계속하시겠습니까?",
                    "This does not look like an Isaac save path. Continue anyway?",
                ),
            )
            if not proceed:
                return
        if self.source_save_path:
            source_name = os.path.basename(self.source_save_path)
            target_name = os.path.basename(normalized)
            if source_name != target_name:
                messagebox.showerror(
                    self._text("경고", "Warning"),
                    self._text("파일 이름이 다릅니다.", "The file names do not match."),
                )
                return
        self.target_save_path = normalized
        self.settings["target_save_path"] = normalized
        self._update_target_display()
        self._save_settings()
        self._apply_auto_overwrite_if_enabled(show_message=True)

    def _on_auto_set_999_toggle(self) -> None:
        enabled = _variable_to_bool(self.auto_set_999_var)
        self.settings["auto_set_999"] = enabled
        self._save_settings()
        if enabled:
            self._apply_auto_999_if_needed()

    def _on_auto_overwrite_toggle(self) -> None:
        enabled = _variable_to_bool(self.auto_overwrite_var)
        self.settings["auto_overwrite"] = enabled
        self._save_settings()
        if enabled:
            self._apply_auto_overwrite_if_enabled(show_message=True)

    def _show_auto_overwrite_help(self) -> None:
        help_window = tk.Toplevel(self)
        help_window.title(self._text("세이브파일 자동 덮어쓰기 안내", "Auto Overwrite Guide"))
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
            font=title_font,
            justify="left",
            text=self._text("자동 덮어쓰기 사용 방법", "How to Use Auto Overwrite"),
        )
        title_label.grid(column=0, row=0, sticky="w")

        steps = localization.get_auto_overwrite_steps(self._language_code)
        body_label = ttk.Label(
            container,
            text="\n\n".join(steps),
            font=body_font,
            justify="left",
            wraplength=460,
        )
        body_label.grid(column=0, row=1, sticky="w", pady=(12, 18))

        close_button = ttk.Button(
            container,
            command=help_window.destroy,
            text=self._text("확인", "OK"),
        )
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
        if not _variable_to_bool(self.auto_set_999_var):
            return
        if self.data is None or not self.filename:
            return
        self.set_donation_greed_eden_to_max(auto_trigger=True)

    def _apply_auto_overwrite_if_enabled(
        self, *, show_message: bool = False, prefer_loaded_file: bool = False
    ) -> None:
        if not _variable_to_bool(self.auto_overwrite_var):
            return
        if getattr(self, "_auto_overwrite_executed", False):
            return
        has_source = bool(self.source_save_path)
        if prefer_loaded_file and self.filename:
            has_source = has_source or os.path.exists(self.filename)
        if not has_source or not self.target_save_path:
            return
        success = self._overwrite_target_save(
            show_message=show_message, prefer_loaded_file=prefer_loaded_file
        )
        if success:
            self._auto_overwrite_executed = True

    def _overwrite_target_save_from_button(self) -> None:
        self._overwrite_target_save(show_message=True, prefer_loaded_file=False)

    def _overwrite_target_save(
        self, *, show_message: bool, prefer_loaded_file: bool
    ) -> bool:
        target = self.target_save_path
        if not target:
            if show_message:
                messagebox.showwarning(
                    self._text("경로 없음", "Missing Paths"),
                    self._text(
                        "원본과 덮어쓸 세이브파일을 모두 선택해주세요.",
                        "Please select both the source and target save files.",
                    ),
                )
            return False

        source = self.source_save_path

        if prefer_loaded_file and self.filename:
            loaded_source = self.filename
            if os.path.exists(loaded_source):
                if not source or not self._paths_equal(source, loaded_source):
                    source = loaded_source
                if not self._paths_equal(self.source_save_path, loaded_source):
                    self.source_save_path = loaded_source
                    self.settings["source_save_path"] = loaded_source
                    self._update_source_display()
                    self._save_settings()
            else:
                loaded_source = ""

        if not source:
            if show_message:
                messagebox.showwarning(
                    self._text("경로 없음", "Missing Paths"),
                    self._text(
                        "원본과 덮어쓸 세이브파일을 모두 선택해주세요.",
                        "Please select both the source and target save files.",
                    ),
                )
            return False

        if not os.path.exists(source):
            messagebox.showerror(
                self._text("덮어쓰기 실패", "Overwrite Failed"),
                self._text("원본 세이브파일을 찾을 수 없습니다.", "The source save file could not be found."),
            )
            return False
        target_dir = os.path.dirname(target)
        if target_dir and not os.path.exists(target_dir):
            messagebox.showerror(
                self._text("덮어쓰기 실패", "Overwrite Failed"),
                self._text(
                    "덮어쓸 세이브파일 경로를 찾을 수 없습니다.",
                    "The target save path could not be found.",
                ),
            )
            return False
        try:
            shutil.copyfile(source, target)
        except OSError as exc:
            messagebox.showerror(
                self._text("덮어쓰기 실패", "Overwrite Failed"),
                self._text("세이브파일을 덮어쓰지 못했습니다.", "Could not overwrite the save file.")
                + f"\n{exc}",
            )
            return False
        if show_message:
            messagebox.showinfo(
                self._text("덮어쓰기 완료", "Overwrite Complete"),
                self._text("원본 세이브파일을 덮어썼습니다.", "The source save file has been copied."),
            )
        return True

    def open_save_file(self) -> None:
        filename = filedialog.askopenfilename(
            title=self._text("아이작 세이브파일 선택", "Select Isaac Save File"),
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

    def _get_savefile_initial_directory(self, *paths: str) -> str:
        for path in paths:
            if not path:
                continue
            directory = os.path.dirname(path)
            if directory and os.path.exists(directory):
                return directory
        return self._get_initial_directory()

    def _load_file(self, filename: str, *, show_errors: bool = True) -> bool:
        normalized = os.path.abspath(filename)
        try:
            with open(normalized, "rb") as file:
                data = file.read()
        except OSError as exc:
            if show_errors:
                messagebox.showerror(
                    self._text("파일 오류", "File Error"),
                    self._text("세이브 파일을 열 수 없습니다.", "Unable to open the save file.")
                    + f"\n{exc}",
                )
            return False

        self.data = data
        self.filename = normalized
        basename = os.path.basename(normalized)
        self._update_loaded_file_display()
        self.settings["last_path"] = normalized
        self._save_settings()
        self.refresh_current_values()
        self._apply_auto_999_if_needed()
        return True

    def _on_remember_path_toggle(self) -> None:
        remember_enabled = _variable_to_bool(self.remember_path_var)
        self.settings["remember_path"] = remember_enabled
        if remember_enabled and self.filename:
            self.settings["last_path"] = self.filename
        self._save_settings()

    def _open_remembered_file_if_available(self) -> None:
        if not _variable_to_bool(self.remember_path_var):
            return
        last_path_setting = self.settings.get("last_path")
        if not isinstance(last_path_setting, str) or not last_path_setting:
            return
        if not os.path.exists(last_path_setting):
            messagebox.showwarning(
                self._text("자동 열기 실패", "Auto Open Failed"),
                self._text(
                    "저장된 세이브 파일 경로를 찾을 수 없습니다. 새로 선택해주세요.",
                    "The stored save file path could not be found. Please choose a new file.",
                ),
            )
            self.loaded_file_var.set(self._default_loaded_text)
            return
        if not self._load_file(last_path_setting, show_errors=False):
            messagebox.showwarning(
                self._text("자동 열기 실패", "Auto Open Failed"),
                self._text(
                    "저장된 세이브 파일을 불러오지 못했습니다. 파일이 사용 중인지 확인해주세요.",
                    "Could not open the stored save file. Please ensure it is not in use.",
                ),
            )
            self.loaded_file_var.set(self._default_loaded_text)

    def _reload_save_file_if_enabled(self) -> bool:
        if not _variable_to_bool(self.remember_path_var):
            return True

        candidate_paths: list[str] = []
        if self.filename:
            candidate_paths.append(self.filename)

        last_path_setting = self.settings.get("last_path")
        if (
            isinstance(last_path_setting, str)
            and last_path_setting
            and not any(
                self._paths_equal(last_path_setting, candidate)
                for candidate in candidate_paths
            )
        ):
            candidate_paths.append(last_path_setting)

        existing_path: str | None = None
        for path in candidate_paths:
            if not path:
                continue
            if not os.path.exists(path):
                continue
            existing_path = path
            if self._load_file(path, show_errors=False):
                return True

        if existing_path is None:
            message = self._text(
                "저장된 세이브 파일 경로를 찾을 수 없습니다. 새로 선택해주세요.",
                "The stored save file path could not be found. Please choose a new file.",
            )
        else:
            message = self._text(
                "저장된 세이브 파일을 불러오지 못했습니다. 파일이 사용 중인지 확인해주세요.",
                "Could not open the stored save file. Please ensure it is not in use.",
            )

        messagebox.showwarning(
            self._text("자동 불러오기 실패", "Auto Load Failed"),
            message,
        )
        return False

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
            english_ui = loaded.get("english_ui")
            if isinstance(english_ui, bool):
                settings["english_ui"] = english_ui
            language_code = loaded.get("language")
            if isinstance(language_code, str):
                settings["language"] = language_code
            highlight_setting = loaded.get("highlight_locked_items")
            if isinstance(highlight_setting, bool):
                settings["highlight_locked_items"] = highlight_setting
            secret_highlight_setting = loaded.get("highlight_locked_secrets")
            if isinstance(secret_highlight_setting, bool):
                settings["highlight_locked_secrets"] = secret_highlight_setting
        return settings

    def _save_settings(self) -> None:
        settings_to_save = DEFAULT_SETTINGS.copy()
        settings_to_save["remember_path"] = _variable_to_bool(self.remember_path_var)
        last_path_setting = self.settings.get("last_path")
        if isinstance(last_path_setting, str):
            settings_to_save["last_path"] = last_path_setting
        auto_set_var = getattr(self, "auto_set_999_var", None)
        auto_overwrite_var = getattr(self, "auto_overwrite_var", None)
        settings_to_save["auto_set_999"] = _variable_to_bool(auto_set_var)
        settings_to_save["auto_overwrite"] = _variable_to_bool(auto_overwrite_var)
        settings_to_save["source_save_path"] = self.source_save_path
        settings_to_save["target_save_path"] = self.target_save_path
        language_code = getattr(self, "_language_code", "ko_kr")
        settings_to_save["english_ui"] = localization.is_english(language_code)
        settings_to_save["language"] = language_code
        highlight_var = getattr(self, "_highlight_locked_items_var", None)
        settings_to_save["highlight_locked_items"] = _variable_to_bool(highlight_var)
        highlight_secret_var = getattr(self, "_highlight_locked_secrets_var", None)
        settings_to_save["highlight_locked_secrets"] = _variable_to_bool(
            highlight_secret_var
        )
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
            num_bytes = int(config.get("num_bytes", 2))
        except (TypeError, ValueError):
            num_bytes = 2
        try:
            base_offset = section_offsets[1] + 0x4 + int(config["offset"])
            return int(
                script.getInt(self.data, base_offset, num_bytes=num_bytes)
            )
        except Exception:
            return None

    def apply_field(
        self,
        key: str,
        preset: int | None = None,
        *,
        preserve_entry: bool = False,
        reload_before_apply: bool = True,
    ) -> bool:
        if reload_before_apply and not self._reload_save_file_if_enabled():
            return False
        if key not in self._numeric_config:
            return False

        if self.data is None or not self.filename:
            messagebox.showwarning(
                self._text("파일 없음", "No File"),
                self._text("먼저 세이브 파일을 열어주세요.", "Please open a save file first."),
            )
            return False

        vars_map = self._numeric_vars[key]
        entry_var = vars_map["entry"]
        config = self._numeric_config[key]
        description_value = config.get("description")
        if isinstance(description_value, tuple):
            description_ko, description_en = description_value
        else:
            description_ko = description_en = str(description_value)

        raw_value = preset if preset is not None else entry_var.get()
        try:
            new_value = int(raw_value)
        except (TypeError, ValueError):
            messagebox.showerror(
                self._text("유효하지 않은 값", "Invalid Value"),
                self._text(
                    f"{description_ko}에 사용할 정수를 입력해주세요.",
                    f"Please enter a valid integer for {description_en}.",
                ),
            )
            return False

        try:
            num_bytes = int(config.get("num_bytes", 2))
        except (TypeError, ValueError):
            num_bytes = 2
        try:
            section_offsets = script.getSectionOffsets(self.data)
            base_offset = section_offsets[1] + 0x4 + int(config["offset"])
            updated = script.alterInt(
                self.data, base_offset, new_value, num_bytes=num_bytes
            )
            updated_with_checksum = script.updateChecksum(updated)
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            messagebox.showerror(
                self._text("업데이트 실패", "Update Failed"),
                self._text(
                    f"{description_ko} 값을 수정하지 못했습니다.",
                    f"Could not update the {description_en} value.",
                )
                + f"\n{exc}",
            )
            return False

        self.data = updated_with_checksum
        try:
            with open(self.filename, "wb") as file:
                file.write(self.data)
        except OSError as exc:
            messagebox.showerror(
                self._text("저장 실패", "Save Failed"),
                self._text("세이브 파일을 저장하지 못했습니다.", "Could not save the file.")
                + f"\n{exc}",
            )
            return False

        self._propagate_numeric_update(key, new_value, num_bytes)
        self.refresh_current_values(update_entry=not preserve_entry)
        self._apply_auto_overwrite_if_enabled(prefer_loaded_file=True)
        return True

    def _propagate_numeric_update(
        self, key: str, value: int, num_bytes: int
    ) -> None:
        if not self.filename:
            return

        if self.data is None:
            return

        related_paths = self._related_save_paths()
        if not related_paths:
            return

        for path in related_paths:
            try:
                path.write_bytes(self.data)
            except OSError:
                continue

    def _related_save_paths(self) -> list[Path]:
        if not self.filename:
            return []

        current_path = Path(self.filename)
        candidates: set[Path] = set()

        def _maybe_add(path: Path, *, require_exists: bool = True) -> None:
            if path == current_path:
                return
            if require_exists and not path.exists():
                return
            candidates.add(path)

        # Include backup for the currently loaded file if present.
        current_backup = current_path.with_name(current_path.name + ".backup")
        _maybe_add(current_backup)

        base_name = current_path.name
        for source in SAVE_FILENAME_VARIANTS:
            if source not in base_name:
                continue
            for replacement in SAVE_FILENAME_VARIANTS:
                if replacement == source:
                    continue
                alt_name = base_name.replace(source, replacement, 1)
                _maybe_add(current_path.with_name(alt_name), require_exists=False)

        # Also check backup for any alternate path we have already gathered.
        additional_backups: list[Path] = []
        for path in list(candidates):
            backup_path = path.with_name(path.name + ".backup")
            if backup_path.exists():
                additional_backups.append(backup_path)

        for backup in additional_backups:
            _maybe_add(backup)

        return sorted(candidates)

    def set_donation_greed_eden_to_max(self, *, auto_trigger: bool = False) -> None:
        if self.data is None or not self.filename:
            if not auto_trigger:
                messagebox.showwarning(
                    self._text("파일 없음", "No File"),
                    self._text("먼저 세이브 파일을 열어주세요.", "Please open a save file first."),
                )
            return
        original_streak = self._read_numeric_value("streak")

        updated_fields: list[str] = []
        if not auto_trigger and not self._reload_save_file_if_enabled():
            return

        for field_key in ("donation", "greed", "eden"):
            if not self.apply_field(
                field_key,
                preset=999,
                preserve_entry=not auto_trigger,
                reload_before_apply=False,
            ):
                break
            updated_fields.append(field_key)

        if not auto_trigger:
            for field_key in updated_fields:
                entry_var = self._numeric_vars.get(field_key, {}).get("entry")
                if entry_var is not None:
                    entry_var.set("999")

        if original_streak is None:
            return

        current_streak = self._read_numeric_value("streak")
        if current_streak is not None and current_streak != original_streak:
            self.apply_field(
                "streak",
                preset=original_streak,
                preserve_entry=not auto_trigger,
                reload_before_apply=False,
            )

    def set_bestiary_encounters_to_one(self) -> None:
        if not self._ensure_data_loaded():
            return

        def updater(data: bytes) -> bytes:
            return script.ensureBestiaryEncounterMinimum(data, minimum=1)

        if self._apply_update(
            updater,
            self._text("베스티어리를 업데이트하지 못했습니다.", "Failed to update the bestiary."),
        ):
            messagebox.showinfo(
                self._text("완료", "Done"),
                self._text(
                    "모든 베스티어리 조우 수를 1로 설정했습니다.",
                    "All bestiary encounters have been set to 1.",
                ),
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
            messagebox.showerror(
                self._text("읽기 실패", "Read Failed"),
                self._text("값을 불러오지 못했습니다.", "Could not read the requested values.")
                + f"\n{exc}",
            )
            return

        for key in self._numeric_order:
            config = self._numeric_config[key]
            vars_map = self._numeric_vars[key]
            try:
                num_bytes = int(config.get("num_bytes", 2))
            except (TypeError, ValueError):
                num_bytes = 2
            try:
                value = script.getInt(
                    self.data,
                    base_offset + int(config["offset"]),
                    num_bytes=num_bytes,
                )
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
