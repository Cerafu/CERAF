@echo off

title CERAF Lichess Bot Launcher

color 0A



echo ============================================

echo            CERAF LICHESS BOT

echo ============================================

echo.



REM Go to lichess-bot folder

cd /d D:\Chess\lichess-bot



echo Checking Python...

where pypy >nul 2>nul



if %errorlevel%==0 (

    echo Using PyPy...

    pypy lichess-bot.py

) else (

    echo PyPy not found. Using Python...

    py lichess-bot.py

)



echo.

echo ============================================

echo CERAF has stopped.

echo ============================================

pause