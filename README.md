# HAM · Remnanode installer

This maintained fork adds a Russian/English menu, a choice of latest official
Xray or the locally tested **26.7.28**, and Xray-only maintenance without
reinstalling the website, certificate or node configuration.

```bash
git clone https://github.com/VPN-sss/node-setup.git
cd node-setup
sudo bash install.sh
```

**Русский:** сначала выберите язык, затем новую установку или смену только
Xray. При новой установке отдельно выбирается self-steal. Для обслуживания
существующей ноды переустановка запрещена: используйте второй пункт.

### Versions and safety / Версии и защита

- `Latest` resolves the current official Xray release when executed; it is not
  a frozen version. Downloads require an upstream SHA256 digest.
- `Tested 26.7.28` is a Firefox/mihomo compatibility workaround, **not a claim
  that an old release is more secure or universally stable**. On amd64 its
  archive SHA256 is pinned in source.
- The Remnanode agent image stays unchanged. Only Xray is bind-mounted from
  a versioned private directory. Existing foreign Compose overrides are
  refused, not overwritten. `GODEBUG=multipathtcp=0` preserves other options.
- Existing live configuration is syntax-tested before recreation. Only the
  `remnanode` service is recreated; no database or user API mutations occur.
- Existing nodes have an independent **20-minute automatic return**. After
  URL-test, repeated HTTPS and exit-IP checks, keep the version with:

  ```bash
  sudo python3 corectl.py accept --state /opt/remnanode/.ham-xray/STATE_FROM_OUTPUT
  ```

  Restore the previous version with:

  ```bash
  sudo python3 corectl.py rollback --state /opt/remnanode/.ham-xray/STATE_FROM_OUTPUT
  ```

- New nodes are explicitly marked fresh: binary/version checks do **not**
  claim client connectivity before a profile is assigned in the panel.
- For a fresh self-steal certificate, DNS-01 via Cloudflare is the default on
  Enter. The inherited standalone ALPN option requires external port 443 to
  reach its local port 8443; it is not automatic port forwarding.
- A private `/opt/remnanode/profile-template.json` is generated for new nodes.
  Import it into the panel; it contains `minClientVer: "1.8.2"` on REALITY.
  Set the panel host fingerprint to **firefox**. Existing panel profiles are
  never silently modified; the script does not have panel API credentials.
- MPTCP disabling is a process safeguard, **not a Linux security patch**.
  Keep the host kernel updated. Current old profiles need their own review.
- Secrets are entered without echo and stored with restrictive permissions;
  `.env` is parsed as data, not executed as shell code. Do not share `.env`,
  private templates, certificate keys or `.ham-xray` backups.

### Language / Язык

The main menu, version choice, maintenance guidance and principal install
prompts support RU/EN. Some inherited detailed diagnostics and package-manager
output remain English. WARP is optional and disabled unless requested.

### Verification

```bash
python3 -B -m unittest discover -s tests
for script in install.sh legacy-install.sh lib/ui.sh; do bash -n "$script" || exit; done
bash install.sh --help
```

The original upstream installer and its historical documentation follow below;
use the **VPN-sss command above** for these new menus. A full certificate/network
installation must still be verified on the target host; passing unit tests is
not proof of connectivity from every ISP.

---

## Upstream installer

An automated Bash script for deploying a Remnanode with Nginx proxy, a selected web service, and Cloudflare WARP integration.

## 📋 What Does This Script Do?

The script fully configures a server from scratch:

1. **Infrastructure:** Installs Docker Engine and Docker Compose.
2. **SSL Certification:** Installs `acme.sh` and issues **Let's Encrypt** certificates (Standalone mode).
3. **Nginx Proxy:** Configures a proxy server (port `9443`) for secure HTTPS access.
4. **Remnanode:** Installs the node with automatic `SECRET_KEY` and SSL certificate paths.
5. **Security:** Configures `ufw` firewall (only necessary ports are opened).
6. **Cloudflare WARP:** Downloads the WARP client installer.

---

## 🌍 Other Languages

- [Русский](docs/README_RU.md)
- [中文](docs/README_CN.md)

## 🛠 Prerequisites

- **OS:** Ubuntu 22.04+ or Debian 11+.
- **Domain:** Your A-record must point to the server's IP.
- **Permissions:** Run as **root** or with sudo.

## 🚀 Installation

1. Clone the repository:
  ```bash
   git clone https://github.com/VPN-sss/node-setup.git
  ```
2. Navigate to the project folder:
  ```bash
   cd node-setup
  ```
3. Grant execute permissions:
  ```bash
   chmod +x install.sh
  ```
4. Run the installation:
  ```bash
   ./install.sh
  ```

## 🚀 Installation (in one command)

```bash
git clone https://github.com/VPN-sss/node-setup.git && cd node-setup && sudo chmod +x install.sh && sudo ./install.sh
```

## ⌨️ Input Parameters

The script will prompt for:

1. **Email** (for SSL registration).
2. **Domain** (e.g., `node.domain.com`).
3. **SECRET_KEY** (from Remnawave control panel).
4. **Service Selection** (enter a number or press Enter for random).

## 📂 Project Structure

- `/opt/remnanode/` — Node configuration.
- `/opt/remnanode/nginx/` — Nginx configs and SSL keys.
- `/opt/[service-name]/` — Selected web service files.

## ⚠️ Used Ports


| Port  | Service                         |
| ----- | ------------------------------- |
| 443   | xray (or custom)                |
| 9443  | Web Interface (HTTPS)           |
| 2222  | Remnanode Node Port             |
| 40000 | Cloudflare WARP SOCKS5 (closed) |


## Support me

**Tron**: ```TVfpYd9SZuYy9nZw5TwXUrdHTnR5YoSZn1```

**Sol**: ```CxP98kjB2DWE8oUi77tj5Dxgsrf5671i13XGoPws9gwv```
