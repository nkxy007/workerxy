# Container Management - Docker & Podman

## Docker

### Installation

**Ubuntu:**
```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt update
sudo apt install ca-certificates curl gnupg lsb-release -y

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
```

**RedHat:**
```bash
# Remove old versions
sudo dnf remove docker docker-common docker-selinux docker-engine

# Add repository
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
```

### Basic Commands

**Container Management:**
```bash
# Run container
docker run -d --name myapp -p 8080:80 nginx
docker run -it ubuntu /bin/bash  # Interactive
docker run -d -e ENV_VAR=value myimage  # Environment variable

# List containers
docker ps           # Running only
docker ps -a        # All containers

# Start/stop containers
docker start container_name
docker stop container_name
docker restart container_name

# Remove containers
docker rm container_name
docker rm -f container_name  # Force remove running container
docker container prune       # Remove all stopped containers

# Execute commands in container
docker exec -it container_name /bin/bash
docker exec container_name ls /app

# View logs
docker logs container_name
docker logs -f container_name  # Follow logs
docker logs --tail 100 container_name

# Inspect container
docker inspect container_name
docker stats container_name  # Resource usage
```

**Image Management:**
```bash
# Pull image
docker pull nginx
docker pull nginx:1.21

# List images
docker images
docker images -a

# Remove images
docker rmi image_name
docker rmi image_id
docker image prune  # Remove dangling images
docker image prune -a  # Remove unused images

# Build image
docker build -t myapp:v1 .
docker build -t myapp:v1 -f Dockerfile.prod .

# Tag image
docker tag myapp:v1 myregistry.com/myapp:v1

# Push image
docker push myregistry.com/myapp:v1

# Save/load images
docker save myapp:v1 > myapp.tar
docker load < myapp.tar

# Export/import containers
docker export container_name > container.tar
docker import container.tar newimage:tag
```

**Network Management:**
```bash
# List networks
docker network ls

# Create network
docker network create mynetwork
docker network create --driver bridge --subnet 172.20.0.0/16 mynetwork

# Connect container to network
docker network connect mynetwork container_name
docker network disconnect mynetwork container_name

# Inspect network
docker network inspect mynetwork

# Remove network
docker network rm mynetwork
docker network prune  # Remove unused networks
```

**Volume Management:**
```bash
# Create volume
docker volume create myvolume

# List volumes
docker volume ls

# Inspect volume
docker volume inspect myvolume

# Remove volume
docker volume rm myvolume
docker volume prune  # Remove unused volumes

# Use volume in container
docker run -d -v myvolume:/app/data myapp
docker run -d -v /host/path:/container/path myapp  # Bind mount
```

### Docker Compose

**Installation (if not included):**
```bash
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**docker-compose.yml example:**
```yaml
version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html
    networks:
      - webnet
    restart: unless-stopped

  app:
    build: ./app
    environment:
      - DATABASE_URL=postgresql://db:5432/mydb
    depends_on:
      - db
    networks:
      - webnet
    volumes:
      - app-data:/app/data

  db:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=mydb
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - webnet

networks:
  webnet:

volumes:
  app-data:
  db-data:
```

**Commands:**
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f
docker compose logs -f web

# List services
docker compose ps

# Restart services
docker compose restart

# Build images
docker compose build

# Pull images
docker compose pull

# Execute command
docker compose exec web /bin/bash

# Scale services
docker compose up -d --scale app=3
```

### Dockerfile Best Practices

```dockerfile
# Use specific version tags
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files first (better caching)
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Change ownership
RUN chown -R nodejs:nodejs /app

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD node healthcheck.js

# Start application
CMD ["node", "server.js"]
```

**Multi-stage build:**
```dockerfile
# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
USER node
CMD ["node", "dist/server.js"]
```

## Podman

### Installation

**Ubuntu:**
```bash
sudo apt update
sudo apt install podman -y
```

**RedHat:**
```bash
sudo dnf install podman -y
```

### Basic Commands

Podman commands are nearly identical to Docker:

```bash
# Run container
podman run -d --name myapp -p 8080:80 nginx

# List containers
podman ps
podman ps -a

# Manage containers
podman start/stop/restart container_name
podman rm container_name

# Images
podman pull nginx
podman images
podman rmi image_name

# Logs and exec
podman logs container_name
podman exec -it container_name /bin/bash

# Networks
podman network create mynetwork
podman network ls

# Volumes
podman volume create myvolume
podman volume ls
```

### Rootless Containers

Podman's key advantage - run containers without root:

```bash
# Run as regular user (no sudo needed)
podman run -d --name web -p 8080:80 nginx

# Check user namespace
podman info | grep -A 3 runRoot

# Configure subuid/subgid
cat /etc/subuid
cat /etc/subgid
```

### Pods (Kubernetes-like)

```bash
# Create pod
podman pod create --name mypod -p 8080:80

# Run containers in pod
podman run -d --pod mypod --name web nginx
podman run -d --pod mypod --name app myapp

# List pods
podman pod ls

# Inspect pod
podman pod inspect mypod

# Stop/start pod
podman pod stop mypod
podman pod start mypod

# Remove pod
podman pod rm mypod

# Generate Kubernetes YAML from pod
podman generate kube mypod > mypod.yaml

# Create pod from Kubernetes YAML
podman play kube mypod.yaml
```

### Systemd Integration

Generate systemd service for container:

```bash
# Run container
podman run -d --name myapp -p 8080:80 nginx

# Generate systemd unit file
podman generate systemd --new --name myapp > ~/.config/systemd/user/myapp.service

# Enable service
systemctl --user enable myapp.service
systemctl --user start myapp.service

# For system-wide service (as root)
sudo podman generate systemd --new --name myapp > /etc/systemd/system/myapp.service
sudo systemctl enable myapp.service
sudo systemctl start myapp.service
```

### Podman Compose

**Installation:**
```bash
# Ubuntu
sudo apt install podman-compose -y

# RedHat
sudo dnf install podman-compose -y

# Or via pip
pip3 install podman-compose
```

**Usage:**
```bash
# Use same docker-compose.yml syntax
podman-compose up -d
podman-compose down
podman-compose logs -f
```

## Security Best Practices

### Docker Security

**1. Use official images:**
```bash
docker pull nginx  # Official
docker pull nginx:1.21-alpine  # Minimal base
```

**2. Scan images for vulnerabilities:**
```bash
# Using Docker Scout
docker scout cves myimage:tag

# Using Trivy
trivy image myimage:tag
```

**3. Limit container resources:**
```bash
docker run -d \
  --memory="512m" \
  --cpus="1.0" \
  --pids-limit 200 \
  myapp
```

**4. Use read-only filesystem:**
```bash
docker run -d --read-only --tmpfs /tmp myapp
```

**5. Drop capabilities:**
```bash
docker run -d --cap-drop=ALL --cap-add=NET_BIND_SERVICE myapp
```

**6. Use secrets:**
```bash
# Docker Swarm secrets
echo "my_password" | docker secret create db_password -
docker service create --secret db_password myapp
```

### Podman Security

Podman is rootless by default, providing better isolation:

```bash
# Run without root
podman run -d myapp

# Additional security
podman run -d \
  --security-opt no-new-privileges \
  --cap-drop=ALL \
  myapp
```

## Monitoring & Troubleshooting

### Resource Monitoring

```bash
# Docker
docker stats
docker stats --no-stream
docker system df  # Disk usage

# Podman
podman stats
podman system df
```

### Cleanup

```bash
# Docker - remove all stopped containers, unused images, networks, volumes
docker system prune -a --volumes

# Podman
podman system prune -a --volumes
```

### Debugging

```bash
# Check container logs
docker logs --tail 100 container_name

# Inspect container
docker inspect container_name | jq '.[0].State'

# Check resource limits
docker inspect container_name | jq '.[0].HostConfig.Memory'

# Debug networking
docker exec container_name ip addr
docker exec container_name ping other_container

# Check processes
docker top container_name
```

## Registry Management

### Private Registry

**Docker Registry:**
```bash
# Run registry
docker run -d -p 5000:5000 --name registry \
  -v /mnt/registry:/var/lib/registry \
  registry:2

# Push to private registry
docker tag myapp localhost:5000/myapp
docker push localhost:5000/myapp

# Pull from private registry
docker pull localhost:5000/myapp
```

**Harbor (production-ready):**
```bash
# Download Harbor
wget https://github.com/goharbor/harbor/releases/download/v2.8.0/harbor-offline-installer-v2.8.0.tgz
tar xzvf harbor-offline-installer-v2.8.0.tgz
cd harbor

# Configure
cp harbor.yml.tmpl harbor.yml
vim harbor.yml  # Edit hostname, ports, etc.

# Install
sudo ./install.sh
```

## Container Orchestration

For production, consider:
- **Docker Swarm** - Simple clustering
- **Kubernetes** - Industry standard, complex
- **Nomad** - HashiCorp alternative
- **OpenShift** - Enterprise Kubernetes (RedHat)

Basic Docker Swarm:
```bash
# Initialize swarm
docker swarm init

# Deploy service
docker service create --name web --replicas 3 -p 80:80 nginx

# Scale service
docker service scale web=5

# Update service
docker service update --image nginx:1.21 web
```