folders = data engine icons
targetdir = /usr/share/ibus-combo
install: clean
	mkdir -p $(targetdir)
	cp -R $(folders) $(targetdir)
	cp ibus-engine-combo /usr/lib/ibus/ibus-engine-combo
	cp combo.xml /usr/share/ibus/component/combo.xml
uninstall:
	rm -R $(targetdir)
	rm /usr/lib/ibus/ibus-engine-combo
	rm /usr/share/ibus/component/combo.xml
clean:
	-rm engine/*~ > /dev/null 2>&1
