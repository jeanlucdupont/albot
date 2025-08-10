#!/usr/bin/env bash
set -euo pipefail

# Ubuntu "CTI Edition" hardening 
# Purpose: safe(r) passive collection via Tor Browser + torsocks, minimal traces.

# ---- Helpers ----
ok()  { echo "[+] $*"; }
die() { echo "[!] $*" >&2; exit 1; }
require_root() { [ "$(id -u)" -eq 0 ] || die "Run as root"; }
require_root

# ---- 0) Sanity ----
ok "Updating APT cache and base system..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get dist-upgrade -y

# ---- 1) Remove/disable telemetry-ish bits ----
ok "Removing common telemetry/crash-reporting packages..."
apt-get purge -y popularity-contest apport whoopsie || true
systemctl disable --now whoopsie.service || true
systemctl mask whoopsie.service || true
systemctl disable --now apport.service || true
systemctl mask apport.service || true

# ---- 2) Install tooling ----
ok "Installing CTI tooling (Tor, Tor Browser launcher, sandbox, etc.)..."
apt-get install -y \
  tor torsocks torbrowser-launcher \
  ufw apparmor apparmor-utils apparmor-profiles \
  firejail firejail-profiles \
  macchanger jq curl wget nano unzip \
  net-tools dnsutils

# Ensure AppArmor is on
ok "Ensuring AppArmor is enabled at boot..."
if ! grep -q "apparmor=1" /etc/default/grub; then
  sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\)"/\1 apparmor=1 security=apparmor"/' /etc/default/grub || true
  update-grub || true
fi
systemctl enable apparmor
systemctl start apparmor

# ---- 3) UFW minimal stance ----
ok "Configuring UFW (allow loopback; otherwise default deny incoming; allow outgoing)..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 9050/tcp  # local Tor SOCKS (if used)
ufw --force enable

# NOTE: We’re not forcing transparent Toring with firewall redirection
# to avoid breaking updates and package mirrors. Use Tor Browser for .onion,
# and torsocks for CLI fetches when needed.

# ---- 4) System logging minimization ----
ok "Minimizing persistent logs (journald size & volatility)..."
mkdir -p /etc/systemd/journald.conf.d
cat >/etc/systemd/journald.conf.d/cti.conf <<'EOF'
[Journal]
# Keep logs in RAM only; nothing on disk.
Storage=volatile
# Limit size and retention in RAM
RuntimeMaxUse=64M
RuntimeMaxFileSize=16M
MaxFileSec=1day
EOF
systemctl restart systemd-journald

# Bash history hygiene for all users created later
ok "Reducing shell history footprint..."
cat >/etc/profile.d/cti_history.sh <<'EOF'
# Minimal, session-only history; clear on logout
export HISTSIZE=0
export HISTFILESIZE=0
unset HISTFILE
EOF
chmod 0644 /etc/profile.d/cti_history.sh

# ---- 5) MAC randomization ----
ok "Enabling NetworkManager MAC randomization (scan + connect)..."
mkdir -p /etc/NetworkManager/conf.d
cat >/etc/NetworkManager/conf.d/00-macrandomize.conf <<'EOF'
[device]
wifi.scan-rand-mac-address=yes

[connection]
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=random
EOF
systemctl restart NetworkManager || true

# ---- 6) Optional IPv6 hardening (comment out if you need IPv6) ----
ok "Disabling IPv6 to reduce leak surface (optional)..."
cat >/etc/sysctl.d/99-disable-ipv6.conf <<'EOF'
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
EOF
sysctl --system

# ---- 7) Create dedicated non-admin CTI user ----
CTI_USER="ctiops"
if ! id "$CTI_USER" &>/dev/null; then
  ok "Creating non-admin user: ${CTI_USER}"
  adduser --disabled-password --gecos "" "$CTI_USER"
  # No sudo for CTI user; keep admin separate
  usermod -L "$CTI_USER" || true
  passwd -d "$CTI_USER" || true
  # Yeah! Change the password at first boot.
  # Create a login with SSH *disabled* by default (local console only).
fi

# ---- 8) Tor Browser bootstrap (user space) ----
ok "Preparing Tor Browser bootstrap script for ${CTI_USER}..."
mkdir -p /home/${CTI_USER}/bin
cat >/home/${CTI_USER}/bin/tor-browser.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# Launch Tor Browser via torbrowser-launcher; auto-update within its sandbox
torbrowser-launcher
EOF
chmod +x /home/${CTI_USER}/bin/tor-browser.sh
chown -R ${CTI_USER}:${CTI_USER} /home/${CTI_USER}

# ---- 9) Torsocks convenience + firejail wrappers ----
ok "Setting up torsocks and firejail convenience aliases for ${CTI_USER}..."
cat >>/home/${CTI_USER}/.bashrc <<'EOF'

# CTI convenience aliases: run CLI through Tor & sandbox browsers
alias tcurl='torsocks curl -sSL'
alias twget='torsocks wget'
alias tjq='torsocks jq'
alias firefox_sbx='firejail --profile=firefox.profile firefox'
alias chromium_sbx='firejail --profile=chromium.profile chromium || firejail chromium-browser'

echo "[CTI] Use Tor Browser for .onion work; use tcurl/twget for Tor-routed CLI."
EOF
chown ${CTI_USER}:${CTI_USER} /home/${CTI_USER}/.bashrc

# ---- 10) Disable “guest” & unnecessary services ----
ok "Disabling guest session (if using lightdm) and common extras..."
if [ -f /etc/lightdm/lightdm.conf ]; then
  sed -i 's/^#*allow-guest=.*/allow-guest=false/' /etc/lightdm/lightdm.conf || true
fi

systemctl disable --now avahi-daemon.socket avahi-daemon.service || true
systemctl disable --now cups.service cups.socket || true

# ---- 11) Unattended security updates (base OS only) ----
ok "Enabling unattended upgrades for security patches..."
apt-get install -y unattended-upgrades
dpkg-reconfigure -fnoninteractive unattended-upgrades

# ---- 12) Final notes ----
ok "Hardening complete. REBOOT recommended."
echo
echo "Next steps:"
echo " 1) Reboot."
echo " 2) Log in as '${CTI_USER}' (local console)."
echo " 3) Run: ~/bin/tor-browser.sh  (first run downloads Tor Browser)."
echo " 4) For CLI over Tor, use: tcurl/twget (torsocks)."
echo
echo "Remember: keep this laptop dedicated."
