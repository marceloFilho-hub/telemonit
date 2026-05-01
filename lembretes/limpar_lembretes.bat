@echo off
REM Remove as 3 tarefas de lembrete do Task Scheduler.
REM Rode este arquivo quando os lembretes ja tiverem disparado para limpar.
schtasks /delete /tn "TelemonitReminder_09h" /f
schtasks /delete /tn "TelemonitReminder_13h" /f
schtasks /delete /tn "TelemonitReminder_17h" /f
echo.
echo Lembretes removidos. Ate a proxima.
pause
