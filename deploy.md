# Digital Ocean Deployment Guide

## Prerequisites
- Digital Ocean account
- Docker installed on your droplet
- Domain name (optional)

## Quick Deployment

### 1. Create a Digital Ocean Droplet
```bash
# Create a droplet with Docker pre-installed
# Recommended: 2GB RAM, 1 vCPU minimum for thumbnail generation
```

### 2. Clone and Setup
```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Clone the repository
git clone https://github.com/your-username/BOLD-VIEWER.git
cd BOLD-VIEWER

# Copy environment file
cp .env_example .env
```

### 3. Configure Environment
Edit the `.env` file with your AWS credentials:
```bash
nano .env
```

Update with your values:
```
SECRET_KEY=your-secure-secret-key-here
AWS_ACCESS_KEY=your-aws-access-key
AWS_SECRET_KEY=your-aws-secret-key
S3_BUCKET_NAME=your-s3-bucket-name
REGION_NAME=your-aws-region
```

### 4. Deploy with Docker Compose
```bash
# Build and start the application
docker-compose up -d

# Check logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 5. Access Your Application
- Open `http://your-droplet-ip:5000` in your browser
- Default login credentials are in your auth system

## Production Optimizations

### 1. Use Nginx Reverse Proxy
Create `/etc/nginx/sites-available/bold-viewer`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for thumbnail generation
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

Enable the site:
```bash
ln -s /etc/nginx/sites-available/bold-viewer /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 2. SSL with Let's Encrypt
```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d your-domain.com
```

### 3. Firewall Setup
```bash
# Allow HTTP, HTTPS, and SSH
ufw allow 22
ufw allow 80
ufw allow 443
ufw enable
```

## Monitoring and Maintenance

### View Logs
```bash
# Application logs
docker-compose logs -f bold-viewer

# System logs
journalctl -u docker
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Backup Thumbnails
```bash
# Backup thumbnail cache
docker run --rm -v bold-viewer_thumbnail_cache:/data -v $(pwd):/backup alpine tar czf /backup/thumbnails-backup.tar.gz -C /data .
```

## Troubleshooting

### Common Issues

1. **Thumbnails not loading**
   - Check ffmpeg installation: `docker-compose exec bold-viewer ffmpeg -version`
   - Check AWS credentials and S3 permissions
   - Verify thumbnail directory permissions

2. **High memory usage**
   - Increase droplet RAM to 4GB for heavy video processing
   - Monitor with: `docker stats`

3. **Slow thumbnail generation**
   - Consider using a larger droplet
   - Implement thumbnail pre-generation for frequently accessed files

### Performance Tuning

For high-traffic deployments:
```yaml
# In docker-compose.yml, increase workers
command: ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "300", "app:app"]
```

## Security Considerations

1. **Environment Variables**: Never commit `.env` to version control
2. **Firewall**: Only expose necessary ports
3. **Updates**: Regularly update the system and Docker images
4. **Monitoring**: Set up log monitoring and alerts
5. **Backups**: Regular backups of configuration and data