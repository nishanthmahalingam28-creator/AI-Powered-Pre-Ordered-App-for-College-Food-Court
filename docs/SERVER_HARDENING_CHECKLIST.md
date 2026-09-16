# Production Server Hardening Checklist

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Target Platform**: Linux (Ubuntu 22.04 LTS / Debian 12)  
**Security Standard**: CIS Linux Benchmark / College Enterprise Security Guidelines  

---

## 1. Access Control & SSH Hardening

- [ ] **SSH Key-Based Authentication Only**:
  Generate an Ed25519 or 4096-bit RSA key pair for all administrative access.
- [ ] **Disable Root Login & Password Authentication**:
  In `/etc/ssh/sshd_config`:
  ```ini
  PermitRootLogin no
  PasswordAuthentication no
  PubkeyAuthentication yes
  ChallengeResponseAuthentication no
  X11Forwarding no
  MaxAuthTries 3
  ClientAliveInterval 300
  ClientAliveCountMax 2
  ```
- [ ] **Restart SSH Service**:
  `sudo systemctl restart sshd`
- [ ] **Dedicated Administrative Sudo User**:
  Never execute daily commands as root. Use a dedicated user in `sudoers` with individual audit tracking.

---

## 2. Network Firewall & Port Isolation

- [ ] **Uncomplicated Firewall (UFW) Configuration**:
  ```bash
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow 22/tcp   # SSH (or custom port)
  sudo ufw allow 80/tcp   # HTTP (for Let's Encrypt renewal & redirect)
  sudo ufw allow 443/tcp  # HTTPS (secure web traffic)
  sudo ufw enable
  ```
- [ ] **Strict Database Isolation**:
  MySQL (Port 3306) must **NEVER** be opened to external interfaces. Verify binding to `127.0.0.1` or docker bridge network in `/etc/mysql/mysql.conf.d/mysqld.cnf`:
  ```ini
  bind-address = 127.0.0.1
  ```
- [ ] **Internal WSGI Isolation**:
  Gunicorn (Port 5000) must bind strictly to `127.0.0.1` and be accessed solely via the Nginx reverse proxy.

---

## 3. System & Kernel Security

- [ ] **Automatic Security Updates**:
  Enable unattended upgrades for critical kernel and package vulnerabilities:
  ```bash
  sudo apt-get install unattended-upgrades
  sudo dpkg-reconfigure --priority=low unattended-upgrades
  ```
- [ ] **Shared Memory Hardening**:
  Add to `/etc/fstab`:
  ```text
  tmpfs /run/shm tmpfs defaults,noexec,nosuid 0 0
  ```
- [ ] **SYN Flood & Network Protection**:
  In `/etc/sysctl.d/99-security.conf`:
  ```ini
  net.ipv4.tcp_syncookies = 1
  net.ipv4.conf.all.rp_filter = 1
  net.ipv4.conf.default.rp_filter = 1
  net.ipv4.conf.all.accept_source_route = 0
  net.ipv4.conf.default.accept_source_route = 0
  ```
  Apply changes: `sudo sysctl --system`

---

## 4. Process & Service Isolation

- [ ] **Unprivileged Service Execution**:
  Run Gunicorn and Flask under the dedicated unprivileged system user `www-data` or `foodcourt`. Never execute the WSGI application as `root`.
- [ ] **Docker Security**:
  - The application container runs as non-root user `foodcourt` (UID 1001).
  - Do not expose the Docker socket `/var/run/docker.sock` to application containers.
  - Apply container memory and CPU limits in `docker-compose.yml`.

---

## 5. Log Rotation & Disk Space Governance

- [ ] **Logrotate Configuration**:
  Ensure `/etc/logrotate.d/foodcourt` is configured for daily rotation and gzip compression with 14-day retention:
  ```text
  /var/log/foodcourt/*.log {
      daily
      missingok
      rotate 14
      compress
      delaycompress
      notifempty
      create 0640 www-data www-data
      sharedscripts
      postrotate
          systemctl reload foodcourt > /dev/null 2>/dev/null || true
      endscript
  }
  ```
- [ ] **Disk Usage Monitoring**:
  Install a daily cron script triggering an alert if root or backup filesystem exceeds 85% capacity.
