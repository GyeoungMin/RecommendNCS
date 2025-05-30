@echo off
REM --- qrc 파일을 py로 변환 (항상 최신 반영) ---
pyrcc5 ui/replay.qrc -o ui/replay_rc.py

REM --- 파이썬 프로그램 실행 ---
python replay_ui_main.py

REM --- (선택) 실행 후 잠깐 대기 ---
pause