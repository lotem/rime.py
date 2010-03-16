folders = data engine icons
targetdir = /usr/share/ibus-zime
libexecdir = /usr/lib/ibus-zime
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
