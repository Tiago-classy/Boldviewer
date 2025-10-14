#!/bin/bash

# Digital Ocean Deployment Script for BOLD-VIEWER

echo "🚀 Starting BOLD-VIEWER deployment..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl start docker
    systemctl enable docker
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env_example .env
    echo "⚠️  Please edit .env file with your AWS credentials before continuing"
    exit 1
fi

# Build and start the application
echo "Building and starting BOLD-VIEWER..."
docker-compose down
docker-compose up -d --build

echo "✅ BOLD-VIEWER is starting up..."
echo "📱 Access your application at: http://$(curl -s ifconfig.me):5000"
echo "📋 Check logs with: docker-compose logs -f"
echo "🔧 Check status with: docker-compose ps"