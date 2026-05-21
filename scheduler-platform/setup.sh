#!/bin/bash
# Setup script for local development

set -e

echo "================================"
echo "Scheduler Platform - Local Setup"
echo "================================"

# Create Python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
fi

# Start services
echo "Starting Docker services (PostgreSQL, RabbitMQ, Redis, Prometheus, Grafana)..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Initialize database
echo "Initializing database..."
python -c "from common.database import init_db; init_db()"

echo "================================"
echo "Setup complete!"
echo "================================"
echo ""
echo "Services are now running:"
echo "  - PostgreSQL: localhost:5432"
echo "  - RabbitMQ: localhost:5672 (management: localhost:15672)"
echo "  - Redis: localhost:6379"
echo "  - Prometheus: localhost:9090"
echo "  - Grafana: localhost:3000"
echo ""
echo "Start the API server in one terminal:"
echo "  python api/main.py"
echo ""
echo "Start the scheduler in another terminal:"
echo "  python scheduler/main.py"
echo ""
echo "Start the worker in another terminal:"
echo "  python worker/main.py"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
