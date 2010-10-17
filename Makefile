folders = data engine icons
targetdir = /usr/share/ibus-zime
libexecdir = /usr/lib/ibus-zime
all:
	@echo ':)'
install: clean
	mkdir -p $(targetdir)
	cp -R $(folders) $(targetdir)
	mkdir -p $(libexecdir)
	cp ibus-engine-zime $(libexecdir)/ibus-engine-zime
	cp zime.xml /usr/share/ibus/component/zime.xml
uninstall:
	rm /usr/share/ibus/component/zime.xml
	rm -R $(targetdir)
	rm -R $(libexecdir)
clean:
	-find . -name '*~' -delete
	-find . -name '*.py[co]' -delete
	-find . -name '.*.swp' -delete
restart_ibus:
	ibus-daemon -drx
schema_pinyin: restart_ibus
	(cd data; python zimedb-admin.py -vi Pinyin.txt; python zimedb-admin.py -ki DoublePinyin.txt; python zimedb-admin.py -ki ComboPinyin.txt)
schema_tonal_pinyin: restart_ibus
	(cd data; python make-phrases.py tonal-pinyin; python zimedb-admin.py -vi TonalPinyin.txt)
schema_zhuyin: restart_ibus
	(cd data; python make-phrases.py zhuyin; python zimedb-admin.py -vi Zhuyin.txt)
schema_quick: restart_ibus
	(cd data; python make-phrases.py quick; python zimedb-admin.py -vi Quick.txt)
schema_jyutping: restart_ibus
	(cd data; python make-phrases.py jyutping; python zimedb-admin.py -vi Jyutping.txt)
schema_wu: restart_ibus
	(cd data; python make-phrases.py wu; cat wu-extra-phrases.txt >> wu-phrases.txt; python zimedb-admin.py -vi Wu.txt)
clear_db: restart_ibus
	rm ~/.ibus/zime/zime.db
