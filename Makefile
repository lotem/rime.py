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
	(cd data; python create-schema.py -v Pinyin.txt; python create-schema.py -k DoublePinyin.txt; python create-schema.py -k ComboPinyin.txt)
schema_tonal_pinyin: restart_ibus
	(cd data; python make-phrases.py tonal-pinyin; python create-schema.py -v TonalPinyin.txt)
schema_zhuyin: restart_ibus
	(cd data; python make-phrases.py zhuyin; python create-schema.py -v Zhuyin.txt)
schema_jyutping: restart_ibus
	(cd data; python make-phrases.py jyutping; python create-schema.py -v Jyutping.txt)
schema_wu: restart_ibus
	(cd data; python make-phrases.py wu; cat wu-extra-phrases.txt >> wu-phrases.txt; python create-schema.py -v Wu.txt)
clear_db: restart_ibus
	rm ~/.ibus/zime/zime.db
