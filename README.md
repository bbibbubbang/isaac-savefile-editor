# Isaac Savefile Editor

## 개요
Isaac Savefile Editor는 *The Binding of Isaac: Repentance+* 세이브 데이터를 읽고 수정할 수 있는 오픈 소스 도구입니다. Tkinter 기반 GUI와 파이썬 스크립트를 함께 제공하므로, 직접 항목을 편집하거나 자동화 스크립트를 작성해 사용할 수 있습니다.

## 필수 조건
- Python 3.11 이상
- Tkinter(CPython에 기본 포함)
- `ttkwidgets` 패키지
- (선택) 독립 실행 파일을 만들기 위한 PyInstaller

```bash
pip install ttkwidgets
```

## 설치 및 실행
1. **세이브 파일 백업**: `rep+_persistentgamedata*.dat` 파일을 안전한 위치에 복사해 두세요.
2. **세이브 파일 위치 확인**
   - Steam: `{steam}\Steam\userdata\{steam_id}\250900\remote\rep_persistentgamedata{1|2|3}.dat`
   - Windows(비 Steam): `%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance\persistentgamedata{1|2|3}.dat`
3. **에디터 실행**
   - GUI: `python gui.py`
   - 스크립트: `python script.py`
4. GUI에서는 **Open Isaac Save File** 메뉴로 세이브를 불러오고, 스크립트는 `script.py`의 `filename` 변수를 원하는 경로로 수정하세요.

## GUI 사용법
- **숫자 입력 필드**: 연승, 에덴 토큰, 기부량 등 값을 조정한 뒤 <kbd>Enter</kbd>를 누르면 즉시 저장됩니다.
- **클리어 마크**: 캐릭터를 선택하고 체크박스로 개별 마크를 토글하거나 *Unlock All* 버튼으로 한 번에 해제/해금할 수 있습니다.
- **비밀, 아이템, 도전과제**: 각 탭에서 항목을 잠금/해제하며, 필요 시 전체 해금 스위치를 활용할 수 있습니다.

GUI는 별도의 저장 버튼 없이 세이브 파일에 바로 기록하므로, 항상 최신 백업본을 보관하세요.

## 스크립트 활용법
자동화를 위해 `script.py`의 `filename`을 수정한 뒤 제공되는 헬퍼 함수를 사용해 체크섬을 다시 계산하고 이진 데이터를 작성할 수 있습니다. 예제 코드에는 비밀, 클리어 마크, 기타 플래그를 수정하는 방법이 포함되어 있으니 작업 흐름에 맞게 응용해 보세요.

## 독립 실행 파일 만들기
GUI를 PyInstaller로 묶어 배포할 수 있습니다.

```bash
pyinstaller --onefile -w gui.py
```

생성된 실행 파일을 사용하면 파이썬이 설치되지 않은 환경에도 에디터를 배포할 수 있습니다.

## 주의 사항
이 에디터는 Repentance 온라인 베타와의 호환성이 검증되지 않았습니다. 온라인 플레이 시 동기화 오류가 발생할 수 있으니, 반드시 세이브 파일을 백업하고 개인의 책임 하에 사용하세요.
