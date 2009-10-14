folders = data engine icons
targetdir = /usr/share/ibus-zime
install: clean
	mkdir -p $(targetdir)
	cp -R $(folders) $(targetdir)
	cp ibus-engine-zime /usr/lib/ibus/ibus-engine-zime
	cp zime.xml /usr/share/ibus/component/zime.xml
uninstall:
	rm -R $(targetdir)
	rm /usr/lib/ibus/ibus-engine-zime
	rm /usr/share/ibus/component/zime.xml
clean:
	-rm engine/*~ engine/stylo/*~ > /dev/null 2>&1
