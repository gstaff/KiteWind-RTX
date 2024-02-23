@echo off

rem Activate the virtual environment (you may need to adjust this based on your OS)
call venv\Scripts\activate

echo Virtual environment activated.

rem Check if the user is in a virtual environment
if not defined VIRTUAL_ENV (
    echo Error: You are not in a virtual environment.
    echo Please activate your virtual environment and run this script again.
    pause
    exit /b 1
)

rem Launch app; it should open a tab automatically in the default browser
python .\app.py
pause