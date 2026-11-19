@echo off
rem Whole processing pipeline on the default folders (see README.md); stop with Ctrl+C and rerun to resume.
python -B "%~dp0pipeline.py" all --windows 30 --workers 150
pause
