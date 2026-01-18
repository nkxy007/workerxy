# Database Administration - MySQL & PostgreSQL

## MySQL/MariaDB

### Installation

**Ubuntu:**
```bash
# MySQL
sudo apt update
sudo apt install mysql-server -y
sudo systemctl enable mysql
sudo systemctl start mysql

# MariaDB
sudo apt install mariadb-server -y
sudo systemctl enable mariadb
sudo systemctl start mariadb

# Secure installation
sudo mysql_secure_installation
```

**RedHat:**
```bash
# MySQL
sudo dnf install mysql-server -y
sudo systemctl enable mysqld
sudo systemctl start mysqld

# MariaDB
sudo dnf install mariadb-server -y
sudo systemctl enable mariadb
sudo systemctl start mariadb

# Secure installation
sudo mysql_secure_installation
```

### Basic Administration

**Connect to MySQL:**
```bash
# As root
sudo mysql

# As specific user
mysql -u username -p

# Connect to specific database
mysql -u username -p database_name

# Connect to remote server
mysql -h hostname -u username -p
```

**User Management:**
```sql
-- Create user
CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';
CREATE USER 'username'@'%' IDENTIFIED BY 'password';  -- Any host

-- Grant privileges
GRANT ALL PRIVILEGES ON database.* TO 'username'@'localhost';
GRANT SELECT, INSERT, UPDATE ON database.table TO 'username'@'localhost';
GRANT ALL PRIVILEGES ON *.* TO 'username'@'localhost' WITH GRANT OPTION;

-- Show grants
SHOW GRANTS FOR 'username'@'localhost';

-- Revoke privileges
REVOKE ALL PRIVILEGES ON database.* FROM 'username'@'localhost';

-- Delete user
DROP USER 'username'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Change password
ALTER USER 'username'@'localhost' IDENTIFIED BY 'newpassword';
```

**Database Management:**
```sql
-- List databases
SHOW DATABASES;

-- Create database
CREATE DATABASE dbname CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Drop database
DROP DATABASE dbname;

-- Use database
USE dbname;

-- List tables
SHOW TABLES;

-- Describe table
DESCRIBE tablename;
SHOW CREATE TABLE tablename;

-- Table size
SELECT 
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'dbname'
ORDER BY (data_length + index_length) DESC;
```

### Backup & Restore

**mysqldump:**
```bash
# Backup single database
mysqldump -u root -p dbname > backup.sql

# Backup all databases
mysqldump -u root -p --all-databases > all_backup.sql

# Backup with routines and triggers
mysqldump -u root -p --routines --triggers dbname > backup.sql

# Backup specific tables
mysqldump -u root -p dbname table1 table2 > tables_backup.sql

# Compress backup
mysqldump -u root -p dbname | gzip > backup.sql.gz

# Restore
mysql -u root -p dbname < backup.sql
gunzip < backup.sql.gz | mysql -u root -p dbname
```

**mysqlpump (faster parallel backup):**
```bash
mysqlpump -u root -p --default-parallelism=4 dbname > backup.sql
```

**Physical backup with xtrabackup:**
```bash
# Install
sudo apt install percona-xtrabackup-80 -y  # Ubuntu
sudo dnf install percona-xtrabackup-80 -y  # RedHat

# Full backup
sudo xtrabackup --backup --target-dir=/backup/full

# Prepare backup
sudo xtrabackup --prepare --target-dir=/backup/full

# Restore
sudo systemctl stop mysql
sudo xtrabackup --copy-back --target-dir=/backup/full
sudo chown -R mysql:mysql /var/lib/mysql
sudo systemctl start mysql
```

### Replication

**Master configuration (`/etc/mysql/mysql.conf.d/mysqld.cnf`):**
```ini
[mysqld]
server-id=1
log_bin=/var/log/mysql/mysql-bin.log
binlog_do_db=mydb
```

**Slave configuration:**
```ini
[mysqld]
server-id=2
relay-log=/var/log/mysql/mysql-relay-bin
log_bin=/var/log/mysql/mysql-bin.log
```

**Setup replication:**
```sql
-- On Master
CREATE USER 'repl'@'%' IDENTIFIED BY 'password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
SHOW MASTER STATUS;  -- Note File and Position

-- On Slave
CHANGE MASTER TO
    MASTER_HOST='master_ip',
    MASTER_USER='repl',
    MASTER_PASSWORD='password',
    MASTER_LOG_FILE='mysql-bin.000001',
    MASTER_LOG_POS=12345;

START SLAVE;
SHOW SLAVE STATUS\G
```

### Performance Tuning

**Configuration (`/etc/mysql/mysql.conf.d/mysqld.cnf`):**
```ini
[mysqld]
# InnoDB settings
innodb_buffer_pool_size = 4G  # 70-80% of available RAM
innodb_log_file_size = 512M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# Query cache (deprecated in MySQL 8.0)
query_cache_type = 1
query_cache_size = 256M

# Connection settings
max_connections = 500
max_connect_errors = 100

# Slow query log
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```

**Monitor performance:**
```sql
-- Show processlist
SHOW FULL PROCESSLIST;

-- Kill long-running query
KILL QUERY process_id;

-- Show status
SHOW STATUS;
SHOW VARIABLES;

-- InnoDB status
SHOW ENGINE INNODB STATUS\G
```

## PostgreSQL

### Installation

**Ubuntu:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

**RedHat:**
```bash
sudo dnf install postgresql-server postgresql-contrib -y
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### Basic Administration

**Connect to PostgreSQL:**
```bash
# Switch to postgres user
sudo -i -u postgres
psql

# Connect as specific user
psql -U username -d database

# Connect to remote server
psql -h hostname -U username -d database
```

**User Management:**
```sql
-- Create user
CREATE USER username WITH PASSWORD 'password';

-- Create user with specific privileges
CREATE USER username WITH PASSWORD 'password' CREATEDB CREATEROLE;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE dbname TO username;
GRANT SELECT, INSERT, UPDATE ON TABLE tablename TO username;
GRANT ALL ON ALL TABLES IN SCHEMA public TO username;

-- Show users
\du

-- Change password
ALTER USER username WITH PASSWORD 'newpassword';

-- Delete user
DROP USER username;
```

**Database Management:**
```sql
-- List databases
\l

-- Create database
CREATE DATABASE dbname OWNER username;

-- Drop database
DROP DATABASE dbname;

-- Connect to database
\c dbname

-- List tables
\dt

-- Describe table
\d tablename

-- Table sizes
SELECT 
    schemaname AS schema,
    tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Backup & Restore

**pg_dump:**
```bash
# Backup single database
pg_dump -U postgres dbname > backup.sql

# Backup in custom format (compressed)
pg_dump -U postgres -Fc dbname > backup.dump

# Backup specific tables
pg_dump -U postgres -t tablename dbname > table_backup.sql

# Backup all databases
pg_dumpall -U postgres > all_backup.sql

# Restore
psql -U postgres dbname < backup.sql
pg_restore -U postgres -d dbname backup.dump
```

**Physical backup (pg_basebackup):**
```bash
# Create backup
pg_basebackup -U postgres -D /backup/postgres -Ft -z -P

# Restore - stop PostgreSQL, replace data directory, restart
```

### Replication

**Primary server configuration (`/etc/postgresql/*/main/postgresql.conf`):**
```ini
wal_level = replica
max_wal_senders = 3
wal_keep_size = 64
```

**Create replication user:**
```sql
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'password';
```

**pg_hba.conf on primary:**
```
host    replication     replicator      replica_ip/32           md5
```

**Standby server setup:**
```bash
# Create base backup from primary
pg_basebackup -h primary_ip -D /var/lib/postgresql/*/main -U replicator -P

# Create standby.signal file
touch /var/lib/postgresql/*/main/standby.signal

# Configure postgresql.conf
primary_conninfo = 'host=primary_ip port=5432 user=replicator password=password'

# Start standby
sudo systemctl start postgresql
```

**Check replication:**
```sql
-- On primary
SELECT * FROM pg_stat_replication;

-- On standby
SELECT * FROM pg_stat_wal_receiver;
```

### Performance Tuning

**Configuration (`/etc/postgresql/*/main/postgresql.conf`):**
```ini
# Memory settings
shared_buffers = 4GB          # 25% of RAM
effective_cache_size = 12GB   # 50-75% of RAM
work_mem = 64MB
maintenance_work_mem = 1GB

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query planner
random_page_cost = 1.1        # For SSD
effective_io_concurrency = 200

# Connections
max_connections = 200

# Logging
log_min_duration_statement = 1000  # Log queries > 1s
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

**Monitor performance:**
```sql
-- Active queries
SELECT pid, usename, state, query, now() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Kill query
SELECT pg_terminate_backend(pid);

-- Database statistics
SELECT * FROM pg_stat_database;

-- Index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Cache hit ratio
SELECT 
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit) as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;
```

## Common Troubleshooting

### MySQL Issues

**Can't connect:**
```bash
# Check if running
sudo systemctl status mysql

# Check socket
ls -la /var/run/mysqld/mysqld.sock

# Reset root password
sudo systemctl stop mysql
sudo mysqld_safe --skip-grant-tables &
mysql -u root
mysql> FLUSH PRIVILEGES;
mysql> ALTER USER 'root'@'localhost' IDENTIFIED BY 'newpassword';
mysql> exit
sudo systemctl restart mysql
```

**High memory usage:**
```sql
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW STATUS LIKE 'Innodb_buffer_pool_pages%';
```

**Slow queries:**
```bash
# Enable slow query log
sudo tail -f /var/log/mysql/slow.log

# Analyze with pt-query-digest
sudo pt-query-digest /var/log/mysql/slow.log
```

### PostgreSQL Issues

**Can't connect:**
```bash
# Check if running
sudo systemctl status postgresql

# Check pg_hba.conf
sudo cat /etc/postgresql/*/main/pg_hba.conf

# Check listen_addresses in postgresql.conf
listen_addresses = '*'  # Listen on all interfaces
```

**Connection limit reached:**
```sql
-- Check current connections
SELECT count(*) FROM pg_stat_activity;

-- Show max connections
SHOW max_connections;

-- Kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < NOW() - INTERVAL '30 minutes';
```

**Database bloat:**
```sql
-- Check table bloat
SELECT 
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Vacuum
VACUUM VERBOSE ANALYZE;
VACUUM FULL tablename;  -- Locks table
```

## Monitoring Tools

**MySQL:**
- MySQLTuner: `sudo mysqltuner`
- Percona Toolkit: `pt-query-digest`, `pt-mysql-summary`
- phpMyAdmin for web interface

**PostgreSQL:**
- pg_stat_statements extension
- pgBadger for log analysis
- pgAdmin for web interface

**Both:**
- Prometheus + Grafana
- Datadog, New Relic
- Nagios, Zabbix