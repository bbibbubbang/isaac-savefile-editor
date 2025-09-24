# Isaac Savefile Editor

## 소개
Isaac Savefile Editor는 The Binding of Isaac: Repentance 세이브 데이터를 읽고 수정할 수 있는 오픈 소스 도구입니다. Tkinter 기반 GUI와 파이썬 스크립트를 함께 제공하여 마우스로 간편하게 항목을 변경하거나 자동화 스크립트를 작성할 수 있습니다.

## 요구 사항
- Python 3.11 이상
- Tkinter (CPython에 기본 포함)
- `ttkwidgets` 패키지
- (선택) 독립 실행형 실행 파일을 빌드하려면 PyInstaller

```bash
pip install ttkwidgets
```

## 설치 및 실행
1. **세이브 파일 백업**: `rep_persistentgamedata*.dat` 파일을 안전한 위치에 복사합니다.
2. **세이브 파일 찾기**
   - Steam: `{steam}\Steam\userdata\{steam_id}\250900\remote\rep_persistentgamedata{1|2|3}.dat`
   - Windows (비 Steam): `%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance\persistentgamedata{1|2|3}.dat`
3. **에디터 실행**
   - GUI: `python gui.py`
   - 스크립트: `python script.py`
4. GUI에서 **Open Isaac Save File** 메뉴를 사용하거나 `script.py`의 `filename` 변수를 수정해 세이브 파일을 불러옵니다.

## GUI 사용법
- **숫자 항목**: 연속 승수, 에덴 토큰, 기부 금액 등을 입력한 뒤 <kbd>Enter</kbd>를 누르면 즉시 저장됩니다.
- **클리어 표시**: 캐릭터를 선택한 뒤 체크박스로 각 클리어 마크를 토글하거나 *Unlock All* 버튼으로 한꺼번에 해제/해금할 수 있습니다.
- **비밀, 아이템, 도전과제**: 각 탭에서 항목을 체크/해제해 잠금을 관리하고, 필요 시 일괄 해금 스위치를 사용할 수 있습니다.

GUI는 별도의 저장 버튼 없이 곧바로 세이브 파일을 갱신하므로, 항상 백업본을 유지하세요.

## 스크립트 활용
자동화를 위해 `script.py`의 `filename`을 원하는 세이브 경로로 변경한 뒤 제공된 함수들로 체크섬을 다시 계산하고 데이터를 덮어쓸 수 있습니다. 예제 코드는 비밀, 클리어 마크 등의 플래그를 어떻게 조작하는지 보여주며, 필요에 맞게 수정해 사용할 수 있습니다.

## 독립 실행 파일 만들기
PyInstaller를 사용해 GUI를 단독 실행 파일로 빌드할 수 있습니다.

```bash
pyinstaller --onefile -w gui.py
```

생성된 실행 파일은 파이썬을 설치하지 않은 환경에서도 GUI를 실행할 수 있게 해줍니다.

## 주의 사항
이 도구는 Repentance 온라인 베타 버전에서 검증되지 않았습니다. 사용 시 반드시 세이브 데이터를 백업하고 개인 책임 하에 진행하세요.

---

## English Translation

### Overview
Isaac Savefile Editor is an open-source utility for reading and modifying The Binding of Isaac: Repentance save data. It ships with a Tkinter-based GUI and a Python script so you can edit entries by hand or automate changes.

### Requirements
- Python 3.11 or later
- Tkinter (bundled with CPython)
- `ttkwidgets` package
- (Optional) PyInstaller for standalone builds

```bash
pip install ttkwidgets
```

### Setup and Launch
1. **Back up your save files:** copy your `rep_persistentgamedata*.dat` files somewhere safe.
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
