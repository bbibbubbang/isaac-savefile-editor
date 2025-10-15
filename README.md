<img width="764" height="750" alt="1" src="https://github.com/user-attachments/assets/5648fceb-75a8-4cb6-8825-5ca97334429f" />
<img width="764" height="727" alt="2" src="https://github.com/user-attachments/assets/eaed0e75-95e0-4d88-b3bb-f7a0e6a09591" />
<img width="764" height="727" alt="3" src="https://github.com/user-attachments/assets/de20d3a6-c536-4ad0-868a-ab289e1e919a" />
<img width="962" height="727" alt="4" src="https://github.com/user-attachments/assets/97476ade-8ddc-403e-9b76-ad9880b83fcc" />

# Isaac Savefile Editor

## 소개
Isaac Savefile Editor는 *The Binding of Isaac: Repentance+* 세이브 데이터를 읽고 수정할 수 있는 오픈 소스 도구입니다.
이 도구는 해금할 아이템 등의 도전과제, 챌린지를 *완료* 또는 *미완료* 상태로 변경하여 해금유무를 변경하는 방식입니다.

## 설치 및 실행
1. **세이브 파일 백업**: `rep+_persistentgamedata{1|2|3}.dat` 파일을 안전한 위치에 복사합니다.
2. **세이브 파일 찾기**
   - Steam: `{steam}\Steam\userdata\{스팀아이디}\250900\remote\rep_persistentgamedata{1|2|3}.dat`

## 사용법
게임 실행 중 초기 화면을 제외한 곳에서 덮어쓰기(자동 포함) 시도 시 튕기거나 Corrupted data(손상된 데이터)로 변경되어 세이브파일 사용 불가할 수 있습니다.
설명 전에, 프롤로그를 넘기고 아무것도 하지 않은 곳이 **초기 화면**이라고 합니다. (게임 시작 화면)
new run, continue 등이 있는 곳이 **메뉴 화면**입니다.

**[사전 작업]**
1. 세이브파일을 삭제합니다. 기존 세이브파일은 미리 백업하시는걸 권장합니다.
2. **아이작 세이브파일 열기** 버튼을 눌러 게임 세이브파일을 엽니다.
3. 인게임 메뉴까지 들어간 후 초기 화면으로 다시 돌아옵니다.
4. 해금, 미해금할 아이템, 체크리스트, 기부기계 상태 등 원하는 대로 수정하세요.
5. 인게임 메뉴까지 들어간 후 초기 화면으로 다시 돌아옵니다.
6. 세이브파일을 다른 백업폴더에 **복사**합니다.
7. **원본 세이브파일 열기** 버튼을 눌러 백업폴더에 복사한 세이브파일을 엽니다.
8. **덮어쓰기할 세이브파일 열기** 버튼을 눌러 실제 게임 세이브파일을 선택합니다.
9. **아이작 세이브파일 열기** 버튼을 눌러 백업폴더에 복사한 세이브파일을 엽니다. ⚠️ 이 때 기부 기계, 그리드 기계, 연승, 에덴 토큰, 체크리스트 수정 시 세이브파일 덮어쓰기 후 사전 작업 2번부터 다시 해야 합니다. 나머지 메뉴는 상관없음.

**[인게임 작업]**
1. 덮어쓰기 할 세이브파일을 인게임에서 삭제하고 초기 화면으로 돌아가세요.
2. **세이브파일 덮어쓰기** 버튼을 누르세요.
매 판마다 인게임 작업을 처음부터 하시면 됩니다.

## 주의 사항
사용 시 반드시 세이브 데이터를 백업하고 개인 책임 하에 진행하세요.

---

# Isaac Savefile Editor

## Introduction
Isaac Savefile Editor is an open-source tool that allows you to read and modify save data for *The Binding of Isaac: Repentance+*.
This tool changes the unlock status of items, achievements, and challenges by setting them to either *completed* or *not completed*.

## Installation & Execution
1. **Back up your save file**: Copy the file `rep+_persistentgamedata{1|2|3}.dat` to a safe location.  
2. **Locate your save file**  
   - Steam: `{steam}\Steam\userdata\{steamID}\250900\remote\rep_persistentgamedata{1|2|3}.dat`

## Usage
During gameplay, if you attempt to overwrite (including auto-save) outside of the initial screen, the save file may become Corrupted data, making it unusable.
The initial screen refers to the point after the prologue where you haven’t done anything yet (the game start screen).
The screen showing New Run, Continue, etc., is the menu screen.

[Pre-Setup Steps]
1. Delete the existing save file. It’s strongly recommended to back it up first.
2. Click "Open Isaac Save File" to open your game’s save file.
3. Enter the in-game menu, then return to the initial screen.
4. Modify unlocks, locked items, checklists, donation machines, or anything else as desired.
5. Enter the in-game menu again, then return to the initial screen.
6. Copy the save file to another backup folder.
7. Click "Open Original Save File" and open the save file you just copied to the backup folder.
8. Click "Open Target Save File to Overwrite" and select the actual game save file.
9. Click "Open Isaac Save File" again to open the copy in the backup folder.
⚠️ If you edit donation machines, greed machines, win streaks, Eden tokens, or checklists, you must repeat from step 2 of the pre-setup process after overwriting. Other menus are unaffected.

[In-Game Steps]
1. Delete the save file you intend to overwrite from within the game, then return to the initial screen.
2. Click "Overwrite Save File".
3. Repeat the in-game steps from the beginning before each run.

## Warnings  
Always back up your save data and use at your own risk.
