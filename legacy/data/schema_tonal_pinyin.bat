@call ..\env.bat
@echo installing schema TonalPinyin.

..\WeaselServer.exe /q
python make-phrases.py tonal-pinyin
python zimedb-admin.py -vi TonalPinyin.txt

@pause
