# Isaac Savefile Editor

## 소개
Isaac Savefile Editor는 The Binding of Isaac: Repentance+ 세이브 데이터를 읽고 수정할 수 있는 오픈 소스 도구입니다. Tkinter 기반 GUI와 파이썬 스크립트를 함께 제공하여 마우스로 간편하게 항목을 변경하거나 자동화 스크립트를 작성할 수 있습니다.

## 설치 및 실행
1. **세이브 파일 백업**: `rep+_persistentgamedata*.dat` 파일을 안전한 위치에 복사합니다.
2. **세이브 파일 찾기**
   - Steam: `{steam}\Steam\userdata\{스팀아이디}\250900\remote\rep_persistentgamedata{1|2|3}.dat`
   - Windows (비 Steam): `%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance\persistentgamedata{1|2|3}.dat`

## 사용법
- **숫자 입력 항목**: 기부 머신,에덴 토큰,연승 횟수 등을 입력한 뒤 <kbd>적용</kbd>을 누르면 즉시 저장됩니다.
- **클리어 표시**: 캐릭터를 선택한 뒤 체크박스로 각 클리어 마크를 토글하거나 *Unlock All* 버튼으로 한꺼번에 해제/해금할 수 있습니다.
- **비밀, 아이템, 도전과제**: 각 탭에서 항목을 체크/해제해 잠금을 관리하고, 필요 시 일괄 해금 스위치를 사용할 수 있습니다.

오류 발생을 대비해 항상 백업본을 유지하세요.

## 주의 사항
이 도구는 Repentance+ 온라인 베타 버전에서 검증되지 않았습니다. 온라인 플레이 시 Desync(동기화 오류)가 발생할 수 있습니다. 사용 시 반드시 세이브 데이터를 백업하고 개인 책임 하에 진행하세요.

---

## English Translation

### Overview
Isaac Savefile Editor is an open-source utility for reading and modifying The Binding of Isaac: Repentance+ save data. It ships with a Tkinter-based GUI and a Python script so you can edit entries by hand or automate changes.

### Requirements
- Python 3.11 or later
- Tkinter (bundled with CPython)
- `ttkwidgets` package
- (Optional) PyInstaller for standalone builds

```bash
pip install ttkwidgets
```

### Setup and Launch
1. **Back up your save files:** copy your `rep+_persistentgamedata*.dat` files somewhere safe.
2. **Locate the save file**
   - Steam: `{steam}\Steam\userdata\{steam_id}\250900\remote\rep_persistentgamedata{1|2|3}.dat`
   - Windows (non-Steam): `%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance\persistentgamedata{1|2|3}.dat`
3. **Start the editor**
   - GUI: `python gui.py`
   - Script: `python script.py`
4. Load the save through the GUI's **Open Isaac Save File** menu or by updating the `filename` variable in `script.py`.

### Using the GUI
- **Numeric fields:** adjust streaks, Eden tokens, donation values, and press <kbd>Enter</kbd> to apply the change immediately.
- **Completion marks:** choose a character, toggle individual marks with checkboxes, or use the *Unlock All* buttons for bulk edits.
- **Secrets, items, challenges:** unlock or relock entries per tab, and leverage the provided unlock-all toggles when needed.

The GUI writes directly to the save file without a separate save button—keep backups handy.

### Working with the Script
For automation, update `filename` in `script.py`, then rely on the helper functions to recalculate checksums and write binary data. The included example demonstrates how to modify secrets, completion marks, and other flags; adapt it to your workflow.

### Building a Standalone Executable
You can bundle the GUI with PyInstaller:

```bash
pyinstaller --onefile -w gui.py
```

The resulting binary lets you distribute the editor without requiring Python on the target machine.

### Disclaimer
This editor has not been tested against the Repentance online beta. Use it at your own risk and always keep backups of your save data.
