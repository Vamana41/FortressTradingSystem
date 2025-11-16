# Fortress Trading System - Production Deployment Guide

## 🚀 Overview

This guide covers production deployment of the Fortress Trading System with Docker, including high availability, security, monitoring, and scaling considerations.

## 📋 Prerequisites

### System Requirements
- **CPU**: 4+ cores (8+ recommended for high-frequency trading)
- **RAM**: 8GB+ (16GB+ recommended)
- **Storage**: 100GB+ SSD (500GB+ recommended for historical data)
- **Network**: 1Gbps+ connection with low latency to brokers
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Windows Server 2019+

### Software Requirements
- Docker 20.10+
- Docker Compose 1.29+
- Git
- OpenSSL (for SSL certificates)

## 🔧 Production Deployment Steps

### 1. Server Preparation

#### Ubuntu/Debian
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

#### CentOS/RHEL
```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. SSL Certificate Setup

#### Generate Self-Signed Certificate (for testing)
```bash
mkdir -p ssl
cd ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem \
  -out cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"
cd ..
```

#### Use Let's Encrypt (for production)
```bash
# Install certbot
sudo apt install certbot -y

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to ssl directory
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chmod 644 ssl/cert.pem
sudo chmod 600 ssl/key.pem
```

### 3. Configuration Setup

#### Production Configuration
```bash
# Copy production config template
cp config/example_config.json config/production.json

# Edit production configuration
nano config/production.json
```

#### Key Production Settings
```json
{
  "redis": {
    "host": "redis",
    "port": 6379,
    "db": 0,
    "password": "your-strong-redis-password",
    "ssl": true,
    "socket_keepalive": true,
    "socket_keepalive_options": {}
  },
  "security": {
    "api_key_encryption": true,
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60,
      "burst": 120
    },
    "cors": {
      "enabled": true,
      "allowed_origins": ["https://your-domain.com"]
    },
    "session_timeout": 3600,
    "password_policy": {
      "min_length": 12,
      "require_uppercase": true,
      "require_lowercase": true,
      "require_numbers": true,
      "require_special_chars": true
    }
  },
  "performance": {
    "max_workers": 16,
    "batch_size": 1000,
    "cache_ttl": 300,
    "connection_pool_size": 50,
    "request_timeout": 30
  },
  "monitoring": {
    "enabled": true,
    "metrics_retention_days": 30,
    "alert_thresholds": {
      "cpu_usage": 80,
      "memory_usage": 85,
      "disk_usage": 90,
      "error_rate": 5
    }
  }
}
```

### 4. Environment Variables

Create `.env` file for sensitive configuration:
```bash
# Redis
REDIS_PASSWORD=your-strong-redis-password

# API Keys
OPENALGO_API_KEY=your-openalgo-api-key
AMIBROKER_API_KEY=your-amibroker-api-key

# Encryption
ENCRYPTION_KEY=your-32-character-encryption-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/fortress

# Monitoring
SENTRY_DSN=your-sentry-dsn
PROMETHEUS_ENABLED=true
```

### 5. Docker Deployment

#### Build and Start Services
```bash
# Build the application
docker-compose build

# Start services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

#### Verify Deployment
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Test API endpoints
curl -f http://localhost:8001/api/status

# Check dashboard
curl -f http://localhost/
```

## 📊 Monitoring Setup

### 1. Prometheus Configuration

Create `monitoring/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fortress-trading'
    static_configs:
      - targets: ['fortress-trading:8001']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
```

### 2. Grafana Dashboard

Import dashboard ID `12345` for Fortress Trading System metrics, or create custom dashboards for:
- System performance (CPU, memory, disk)
- Trading metrics (signals/sec, latency, error rates)
- Business metrics (P&L, positions, risk metrics)

### 3. Alerting Setup

Configure alerts for:
- High CPU usage (>80%)
- High memory usage (>85%)
- Redis connection failures
- Trading system errors
- Position size violations
- Risk limit breaches

## 🔒 Security Hardening

### 1. Network Security

#### Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

#### Docker Network Isolation
```yaml
# In docker-compose.yml
networks:
  fortress-network:
    driver: bridge
    internal: false
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 2. Application Security

#### API Authentication
```json
{
  "security": {
    "jwt_secret": "your-jwt-secret-key",
    "token_expiry": 3600,
    "refresh_token_expiry": 86400
  }
}
```

#### Input Validation
- All API endpoints validate input data
- SQL injection prevention
- XSS protection
- CSRF tokens for web forms

### 3. Data Encryption

#### Database Encryption
```bash
# Enable Redis encryption
docker run -d \
  --name redis-encrypted \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --requirepass your-strong-password --tls-port 6379
```

#### File System Encryption
```bash
# Encrypt sensitive directories
sudo apt install ecryptfs-utils
sudo mount -t ecryptfs /var/lib/docker/volumes /var/lib/docker/volumes
```

## 🚀 High Availability Setup

### 1. Redis Cluster

```yaml
# docker-compose.redis-cluster.yml
version: '3.8'

services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes --cluster-enabled yes
    ports:
      - "7000:6379"
    volumes:
      - redis_master_data:/data

  redis-slave1:
    image: redis:7-alpine
    command: redis-server --appendonly yes --cluster-enabled yes --slaveof redis-master 6379
    ports:
      - "7001:6379"
    volumes:
      - redis_slave1_data:/data

  redis-slave2:
    image: redis:7-alpine
    command: redis-server --appendonly yes --cluster-enabled yes --slaveof redis-master 6379
    ports:
      - "7002:6379"
    volumes:
      - redis_slave2_data:/data

volumes:
  redis_master_data:
  redis_slave1_data:
  redis_slave2_data:
```

### 2. Load Balancing

#### HAProxy Configuration
```
global
    maxconn 4096

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httpchk GET /api/status

frontend fortress_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/your-domain.pem
    redirect scheme https if !{ ssl_fc }
    
    default_backend fortress_backend

backend fortress_backend
    balance roundrobin
    server fortress1 172.20.0.2:8001 check
    server fortress2 172.20.0.3:8001 check
    server fortress3 172.20.0.4:8001 check
```

### 3. Database Replication

#### PostgreSQL Master-Slave
```yaml
# docker-compose.db-replication.yml
version: '3.8'

services:
  postgres-master:
    image: postgres:14
    environment:
      POSTGRES_DB: fortress
      POSTGRES_USER: fortress
      POSTGRES_PASSWORD: master-password
    volumes:
      - postgres_master_data:/var/lib/postgresql/data
      - ./init-master.sql:/docker-entrypoint-initdb.d/init.sql

  postgres-slave:
    image: postgres:14
    environment:
      POSTGRES_DB: fortress
      POSTGRES_USER: fortress
      POSTGRES_PASSWORD: slave-password
    volumes:
      - postgres_slave_data:/var/lib/postgresql/data
      - ./init-slave.sql:/docker-entrypoint-initdb.d/init.sql
    depends_on:
      - postgres-master
```

## 📈 Scaling Strategies

### 1. Horizontal Scaling

#### Multiple Trading Instances
```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  fortress-trading-1:
    build: .
    environment:
      - INSTANCE_ID=1
      - REDIS_HOST=redis-cluster
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  fortress-trading-2:
    build: .
    environment:
      - INSTANCE_ID=2
      - REDIS_HOST=redis-cluster
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### 2. Vertical Scaling

#### Resource Allocation
```yaml
# docker-compose.resources.yml
version: '3.8'

services:
  fortress-trading:
    build: .
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

## 🔧 Maintenance Procedures

### 1. Backup Strategy

#### Automated Backups
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/fortress/$DATE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup Redis
docker-compose exec redis redis-cli SAVE
docker cp fortress-redis:/data/dump.rdb $BACKUP_DIR/redis-dump.rdb

# Backup configuration
cp -r config/ $BACKUP_DIR/config/

# Backup logs
cp -r logs/ $BACKUP_DIR/logs/

# Backup database
docker-compose exec postgres pg_dump -U fortress fortress > $BACKUP_DIR/database.sql

# Compress backup
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR.tar.gz s3://your-backup-bucket/fortress/
```

#### Backup Schedule
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh  # Daily at 2 AM
0 3 * * 0 /path/to/weekly-backup.sh  # Weekly on Sunday
```

### 2. Update Procedures

#### Zero-Downtime Updates
```bash
# 1. Pull latest code
git pull origin main

# 2. Build new image
docker-compose build fortress-trading

# 3. Scale up new instances
docker-compose up -d --scale fortress-trading=2 --no-recreate

# 4. Wait for new instances to be ready
sleep 30

# 5. Stop old instances
docker-compose stop fortress-trading

# 6. Scale back to normal
docker-compose up -d --scale fortress-trading=1
```

### 3. Health Checks

#### System Health Script
```bash
#!/bin/bash
# health-check.sh

# Check Redis
docker-compose exec redis redis-cli ping || exit 1

# Check API
curl -f http://localhost:8001/api/status || exit 1

# Check Dashboard
curl -f http://localhost/ || exit 1

# Check Database connection
docker-compose exec postgres pg_isready -U fortress || exit 1

echo "All systems healthy"
```

## 🚨 Disaster Recovery

### 1. Recovery Procedures

#### Complete System Recovery
```bash
#!/bin/bash
# restore.sh
BACKUP_DATE=$1
BACKUP_DIR="/backup/fortress/$BACKUP_DATE"

# Stop services
docker-compose down

# Restore Redis
docker cp $BACKUP_DIR/redis-dump.rdb fortress-redis:/data/dump.rdb
docker-compose start redis

# Restore configuration
cp -r $BACKUP_DIR/config/* config/

# Restore database
docker-compose exec postgres psql -U fortress -d fortress < $BACKUP_DIR/database.sql

# Start services
docker-compose up -d
```

### 2. Failover Procedures

#### Automatic Failover
```yaml
# docker-compose.failover.yml
version: '3.8'

services:
  keepalived:
    image: osixia/keepalived:2.0.20
    cap_add:
      - NET_ADMIN
      - NET_BROADCAST
      - NET_RAW
    network_mode: host
    environment:
      KEEPALIVED_VIRTUAL_IPS: "#PYTHON2BASH:['192.168.1.100']"
      KEEPALIVED_UNICAST_PEERS: "#PYTHON2BASH:['192.168.1.101','192.168.1.102']"
```

## 📊 Performance Monitoring

### 1. Key Metrics

#### System Metrics
- CPU utilization (< 80%)
- Memory usage (< 85%)
- Disk I/O (< 70%)
- Network latency (< 10ms)

#### Application Metrics
- Signal processing latency (< 50ms)
- Order execution time (< 100ms)
- Error rate (< 1%)
- Position update frequency

#### Business Metrics
- P&L trends
- Win/loss ratio
- Maximum drawdown
- Sharpe ratio

### 2. Alerting Rules

#### Critical Alerts
```yaml
# alerts.yml
groups:
  - name: fortress-critical
    rules:
      - alert: HighCPUUsage
        expr: cpu_usage_percent > 80
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High CPU usage detected"
          
      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis server is down"
          
      - alert: HighErrorRate
        expr: error_rate_percent > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
```

## 🎯 Best Practices

### 1. Security
- Use strong passwords and API keys
- Enable SSL/TLS encryption
- Implement proper firewall rules
- Regular security audits
- Keep dependencies updated

### 2. Performance
- Monitor resource usage continuously
- Optimize database queries
- Use connection pooling
- Implement caching strategies
- Regular performance testing

### 3. Reliability
- Implement health checks
- Use circuit breakers
- Set up proper logging
- Create backup strategies
- Test disaster recovery procedures

### 4. Scalability
- Design for horizontal scaling
- Use load balancers
- Implement service discovery
- Monitor scaling triggers
- Plan for capacity growth

## 📞 Support

For production deployment support:
- 📧 Email: support@fortress-trading.com
- 🌐 Documentation: https://docs.fortress-trading.com
- 💬 Community: https://discord.gg/fortress-trading
- 🐛 Issues: https://github.com/yourusername/fortress-trading-system/issues

---

**⚠️ Important**: Always test deployment procedures in a staging environment before applying to production. Trading systems involve real money and require the highest levels of reliability and security.