# Advanced Monitoring & Alerting

## Prometheus + Grafana Stack

### Prometheus Installation

**Ubuntu/RedHat:**
```bash
# Create prometheus user
sudo useradd --no-create-home --shell /bin/false prometheus

# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar -xvf prometheus-2.45.0.linux-amd64.tar.gz
cd prometheus-2.45.0.linux-amd64

# Copy binaries
sudo cp prometheus /usr/local/bin/
sudo cp promtool /usr/local/bin/
sudo chown prometheus:prometheus /usr/local/bin/prometheus
sudo chown prometheus:prometheus /usr/local/bin/promtool

# Create directories
sudo mkdir /etc/prometheus
sudo mkdir /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus
sudo chown prometheus:prometheus /var/lib/prometheus

# Copy config files
sudo cp -r consoles /etc/prometheus/
sudo cp -r console_libraries /etc/prometheus/
sudo cp prometheus.yml /etc/prometheus/
sudo chown -R prometheus:prometheus /etc/prometheus
```

**Prometheus configuration (`/etc/prometheus/prometheus.yml`):**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'mysql'
    static_configs:
      - targets: ['localhost:9104']

  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']
```

**Systemd service (`/etc/systemd/system/prometheus.service`):**
```ini
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus/ \
  --web.console.templates=/etc/prometheus/consoles \
  --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```

**Start Prometheus:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

### Node Exporter (System Metrics)

```bash
# Download
cd /tmp
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar -xvf node_exporter-1.6.0.linux-amd64.tar.gz
sudo cp node_exporter-1.6.0.linux-amd64/node_exporter /usr/local/bin/

# Create user
sudo useradd --no-create-home --shell /bin/false node_exporter
sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter
```

**Systemd service (`/etc/systemd/system/node_exporter.service`):**
```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

### Grafana Installation

**Ubuntu:**
```bash
sudo apt-get install -y software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install grafana -y
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

**RedHat:**
```bash
cat <<EOF | sudo tee /etc/yum.repos.d/grafana.repo
[grafana]
name=grafana
baseurl=https://packages.grafana.com/oss/rpm
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://packages.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF

sudo dnf install grafana -y
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

Access: `http://server-ip:3000` (default login: admin/admin)

### Alert Rules

**Create `/etc/prometheus/alerts.yml`:**
```yaml
groups:
  - name: system_alerts
    interval: 30s
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is {{ $value }}%"

      - alert: HighMemoryUsage
        expr: (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 < 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory available is {{ $value }}%"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"}) * 100 < 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space low on {{ $labels.instance }}"
          description: "{{ $labels.mountpoint }} has {{ $value }}% free space"

      - alert: ServiceDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "{{ $labels.instance }} of job {{ $labels.job }} has been down for more than 2 minutes"

      - alert: HighDiskIO
        expr: rate(node_disk_io_time_seconds_total[5m]) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High disk I/O on {{ $labels.instance }}"
          description: "Disk I/O time is {{ $value }}"
```

### Alertmanager

**Installation:**
```bash
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar -xvf alertmanager-0.26.0.linux-amd64.tar.gz
cd alertmanager-0.26.0.linux-amd64
sudo cp alertmanager /usr/local/bin/
sudo cp amtool /usr/local/bin/

sudo useradd --no-create-home --shell /bin/false alertmanager
sudo mkdir /etc/alertmanager
sudo mkdir /var/lib/alertmanager
sudo chown -R alertmanager:alertmanager /etc/alertmanager /var/lib/alertmanager
```

**Configuration (`/etc/alertmanager/alertmanager.yml`):**
```yaml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@example.com'
  smtp_auth_username: 'alerts@example.com'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'email'
  routes:
    - match:
        severity: critical
      receiver: critical-email
      continue: true
    - match:
        severity: warning
      receiver: warning-email

receivers:
  - name: 'email'
    email_configs:
      - to: 'team@example.com'
        headers:
          Subject: '[Alert] {{ .GroupLabels.alertname }}'

  - name: 'critical-email'
    email_configs:
      - to: 'oncall@example.com'
        headers:
          Subject: '[CRITICAL] {{ .GroupLabels.alertname }}'

  - name: 'warning-email'
    email_configs:
      - to: 'team@example.com'
        headers:
          Subject: '[WARNING] {{ .GroupLabels.alertname }}'

  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Systemd service (`/etc/systemd/system/alertmanager.service`):**
```ini
[Unit]
Description=Alertmanager
After=network.target

[Service]
User=alertmanager
Group=alertmanager
Type=simple
ExecStart=/usr/local/bin/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/var/lib/alertmanager/

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable alertmanager
sudo systemctl start alertmanager
```

## Application Exporters

### MySQL Exporter

```bash
# Install
wget https://github.com/prometheus/mysqld_exporter/releases/download/v0.15.0/mysqld_exporter-0.15.0.linux-amd64.tar.gz
tar -xvf mysqld_exporter-0.15.0.linux-amd64.tar.gz
sudo cp mysqld_exporter-0.15.0.linux-amd64/mysqld_exporter /usr/local/bin/

# Create MySQL user
mysql -u root -p
CREATE USER 'exporter'@'localhost' IDENTIFIED BY 'password';
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'localhost';
FLUSH PRIVILEGES;

# Create config
sudo mkdir /etc/mysqld_exporter
echo "
[client]
user=exporter
password=password
" | sudo tee /etc/mysqld_exporter/.my.cnf
sudo chmod 600 /etc/mysqld_exporter/.my.cnf
```

**Systemd service:**
```ini
[Unit]
Description=MySQL Exporter
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/usr/local/bin/mysqld_exporter \
  --config.my-cnf=/etc/mysqld_exporter/.my.cnf \
  --web.listen-address=:9104

[Install]
WantedBy=multi-user.target
```

### Nginx Exporter

**Enable stub_status in Nginx:**
```nginx
server {
    listen 8080;
    server_name localhost;
    
    location /nginx_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }
}
```

```bash
# Install exporter
wget https://github.com/nginxinc/nginx-prometheus-exporter/releases/download/v0.11.0/nginx-prometheus-exporter_0.11.0_linux_amd64.tar.gz
tar -xvf nginx-prometheus-exporter_0.11.0_linux_amd64.tar.gz
sudo cp nginx-prometheus-exporter /usr/local/bin/
```

**Systemd service:**
```ini
[Unit]
Description=Nginx Exporter
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/usr/local/bin/nginx-prometheus-exporter \
  -nginx.scrape-uri=http://localhost:8080/nginx_status

[Install]
WantedBy=multi-user.target
```

## ELK Stack (Elasticsearch, Logstash, Kibana)

### Elasticsearch

**Installation (Ubuntu/RedHat):**
```bash
# Import GPG key
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg

# Ubuntu
echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
sudo apt update
sudo apt install elasticsearch -y

# RedHat
cat <<EOF | sudo tee /etc/yum.repos.d/elasticsearch.repo
[elasticsearch]
name=Elasticsearch repository for 8.x packages
baseurl=https://artifacts.elastic.co/packages/8.x/yum
gpgcheck=1
gpgkey=https://artifacts.elastic.co/GPG-KEY-elasticsearch
enabled=1
autorefresh=1
type=rpm-md
EOF
sudo dnf install elasticsearch -y

# Start service
sudo systemctl enable elasticsearch
sudo systemctl start elasticsearch
```

### Logstash

```bash
# Ubuntu
sudo apt install logstash -y

# RedHat
sudo dnf install logstash -y

# Start service
sudo systemctl enable logstash
sudo systemctl start logstash
```

**Configuration (`/etc/logstash/conf.d/syslog.conf`):**
```
input {
  file {
    path => "/var/log/syslog"
    type => "syslog"
  }
}

filter {
  if [type] == "syslog" {
    grok {
      match => { "message" => "%{SYSLOGTIMESTAMP:timestamp} %{SYSLOGHOST:hostname} %{DATA:program}(?:\[%{POSINT:pid}\])?: %{GREEDYDATA:message}" }
    }
    date {
      match => [ "timestamp", "MMM  d HH:mm:ss", "MMM dd HH:mm:ss" ]
    }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "syslog-%{+YYYY.MM.dd}"
  }
}
```

### Kibana

```bash
# Ubuntu
sudo apt install kibana -y

# RedHat
sudo dnf install kibana -y

# Configure
sudo vim /etc/kibana/kibana.yml
# server.host: "0.0.0.0"
# elasticsearch.hosts: ["http://localhost:9200"]

# Start service
sudo systemctl enable kibana
sudo systemctl start kibana
```

Access: `http://server-ip:5601`

## Zabbix

### Installation

**Ubuntu:**
```bash
wget https://repo.zabbix.com/zabbix/6.4/ubuntu/pool/main/z/zabbix-release/zabbix-release_6.4-1+ubuntu22.04_all.deb
sudo dpkg -i zabbix-release_6.4-1+ubuntu22.04_all.deb
sudo apt update
sudo apt install zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent -y
```

**RedHat:**
```bash
sudo rpm -Uvh https://repo.zabbix.com/zabbix/6.4/rhel/9/x86_64/zabbix-release-6.4-1.el9.noarch.rpm
sudo dnf clean all
sudo dnf install zabbix-server-mysql zabbix-web-mysql zabbix-apache-conf zabbix-sql-scripts zabbix-selinux-policy zabbix-agent -y
```

**Database setup:**
```bash
# Create database
mysql -u root -p
CREATE DATABASE zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'zabbix'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Import schema
zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql -uzabbix -p zabbix

# Configure
sudo vim /etc/zabbix/zabbix_server.conf
# DBPassword=password

# Start services
sudo systemctl restart zabbix-server zabbix-agent apache2
sudo systemctl enable zabbix-server zabbix-agent apache2
```

Access: `http://server-ip/zabbix`

## Monitoring Best Practices

1. **Set appropriate retention periods** - Balance storage vs historical data needs
2. **Use labels effectively** - Tag metrics with environment, service, instance
3. **Create meaningful dashboards** - Focus on actionable metrics
4. **Set up alerting hierarchies** - Critical, warning, info levels
5. **Avoid alert fatigue** - Don't alert on everything
6. **Monitor the monitors** - Ensure monitoring stack is healthy
7. **Document runbooks** - Link alerts to remediation steps
8. **Regular review** - Update thresholds and alerts as system evolves
9. **Test alerts** - Verify notifications work
10. **Capacity planning** - Monitor trends for future needs

## Common Metrics to Monitor

### System Metrics
- CPU usage (overall and per core)
- Memory usage (used, available, swap)
- Disk usage (space and I/O)
- Network traffic (bandwidth, errors, drops)
- System load average
- Open file descriptors
- Process count

### Application Metrics
- Request rate
- Error rate
- Response time (p50, p95, p99)
- Active connections
- Queue depth
- Cache hit rate

### Database Metrics
- Connections (active, idle)
- Query performance
- Replication lag
- Lock waits
- Buffer pool usage

### Web Server Metrics
- Request rate
- Response codes (2xx, 3xx, 4xx, 5xx)
- Response time
- Active connections
- Bytes transferred