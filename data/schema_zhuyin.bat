@call ..\env.bat
@echo installing schema Zhuyin.

..\WeaselServer.exe /q
python make-phrases.py zhuyin
python zimedb-admin.py -vi Zhuyin.txt

@pause
