.PHONY: install install-service uninstall-service start stop restart status logs

SERVICE := profile-availability
UNIT_DIR := $(if $(XDG_CONFIG_HOME),$(XDG_CONFIG_HOME),$(HOME)/.config)/systemd/user
STATE_DIR := $(if $(XDG_STATE_HOME),$(XDG_STATE_HOME),$(HOME)/.local/state)/$(SERVICE)

install:
	python3 -m venv .venv
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r requirements.txt

install-service: install
	mkdir -p $(UNIT_DIR) $(STATE_DIR)
	sed -e 's|@CHECKOUT@|$(CURDIR)|g' -e 's|@STATE_DIR@|$(STATE_DIR)|g' deploy/$(SERVICE).service > $(UNIT_DIR)/$(SERVICE).service
	systemctl --user daemon-reload
	systemctl --user enable $(SERVICE)
	systemctl --user restart $(SERVICE)
	loginctl enable-linger

uninstall-service:
	systemctl --user disable --now $(SERVICE)
	rm -f $(UNIT_DIR)/$(SERVICE).service
	systemctl --user daemon-reload

start stop restart:
	systemctl --user $@ $(SERVICE)

status:
	-systemctl --user status $(SERVICE)

logs:
	journalctl --user -u $(SERVICE) -f
