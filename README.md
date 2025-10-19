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
3. **메뉴 화면**까지 들어간 후 **초기 화면**으로 다시 돌아옵니다.
4. 해금, 미해금할 아이템, 체크리스트, 기부기계 상태 등 원하는 대로 수정하세요.
5. **메뉴 화면**까지 들어간 후 **초기 화면**으로 다시 돌아옵니다.
6. 세이브파일을 다른 백업폴더에 **복사**합니다.
7. **원본 세이브파일 열기** 버튼을 눌러 백업폴더에 복사한 세이브파일을 엽니다.
8. **덮어쓰기할 세이브파일 열기** 버튼을 눌러 실제 게임 세이브파일을 선택합니다.
9. **아이작 세이브파일 열기** 버튼을 눌러 백업폴더에 복사한 세이브파일을 엽니다. ⚠️ 이 때 수정 시 기부 기계, 그리드 기계, 연승, 에덴 토큰, 체크리스트가 초기화 될 수 있으며, 세이브파일 덮어쓰기 후 사전 작업 2번부터 다시 해야 합니다.

**[인게임 작업]**
1. 덮어쓰기 할 세이브파일을 인게임에서 삭제하고 **초기 화면**으로 돌아가세요.
2. **세이브파일 덮어쓰기** 버튼을 누르세요.
매 판마다 인게임 작업을 처음부터 하시면 됩니다.

## 주의 사항
사용 시 반드시 세이브 데이터를 백업하고 개인 책임 하에 진행하세요.

---

# Isaac Savefile Editor

## Introduction
Isaac Savefile Editor is an open-source tool that allows you to read and modify save data from *The Binding of Isaac: Repentance+*.  
This tool changes the unlock status of items, challenges, and achievements by marking them as *completed* or *incomplete*.

## Installation & Execution
1. **Back up your save file:** Copy the `rep+_persistentgamedata{1|2|3}.dat` file to a safe location.  
2. **Locate the save file**
   - Steam: `{steam}\Steam\userdata\{SteamID}\250900\remote\rep_persistentgamedata{1|2|3}.dat`

## Usage
If you attempt to overwrite (including autosave) your save file while the game is running *outside of the initial screen*, the game may crash or the save file may become corrupted ("Corrupted data").  
Before explaining further, note the following definitions:  
- The **Initial Screen** refers to the screen right after the prologue, where you have not done anything yet (the game start screen).  
- The **Menu Screen** refers to where options like *new run* and *continue* appear.

**[Pre-Setup Steps]**
1. Delete your save file. (It is strongly recommended to back it up beforehand.)  
2. Click **Open Isaac Save File** to load your game save file.  
3. Enter the **Menu Screen**, then return to the **Initial Screen**.  
4. Modify the unlocks, checklists, donation machines, or any other data as desired.  
5. Enter the **Menu Screen** again and return to the **Initial Screen**.  
6. **Copy** the save file to another backup folder.  
7. Click **Open Original Save File** and select the save file copied to your backup folder.  
8. Click **Open Save File to Overwrite** and select your actual game save file.  
9. Click **Open Isaac Save File** to open the copy from your backup folder. ⚠️ During editing, the donation machine, greed machine, streaks, Eden tokens, and checklist may reset. After overwriting, you must repeat from Step 2 of the pre-setup process.

**[In-Game Steps]**
1. Delete the save file you intend to overwrite *in-game*, then return to the **Initial Screen**.  
2. Click **Overwrite Save File**.  
Repeat these in-game steps from the beginning each time you modify your save.

## Caution
Always back up your save data before using this tool. Proceed at your own risk.
