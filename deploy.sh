#!/bin/bash

# ============================================
# TELEGRAM SHOP BOT - DEPLOY SCRIPT
# Chạy 1 lệnh để deploy bot trên VPS
# ============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Bắt đầu deploy Telegram Shop Bot...${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Khuyên dùng: Chạy với sudo để cài đặt đầy đủ${NC}"
fi

# Update system
echo -e "${GREEN}📦 Cập nhật hệ thống...${NC}"
apt-get update -qq

# Install Docker if not exists
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}🐳 Cài đặt Docker...${NC}"
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo -e "${GREEN}✅ Docker đã được cài đặt${NC}"
fi

# Install Docker Compose if not exists
if ! command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}🐳 Cài đặt Docker Compose...${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo -e "${GREEN}✅ Docker Compose đã được cài đặt${NC}"
fi

# Create .env if not exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Chưa có file .env${NC}"
    
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}📝 Đã tạo .env từ .env.example${NC}"
        echo -e "${RED}❗ Hãy chỉnh sửa file .env trước khi chạy bot:${NC}"
        echo -e "   nano .env"
        exit 1
    else
        echo -e "${RED}❌ Không tìm thấy .env.example${NC}"
        exit 1
    fi
fi

# Validate .env
if grep -q "your_telegram_bot_token" .env; then
    echo -e "${RED}❌ Chưa cấu hình BOT_TOKEN trong .env${NC}"
    echo -e "   nano .env"
    exit 1
fi

# Create data directory
mkdir -p data

# Stop old container if running
echo -e "${GREEN}🛑 Dừng container cũ (nếu có)...${NC}"
docker-compose down 2>/dev/null || true

# Build and run
echo -e "${GREEN}🔨 Build và khởi chạy bot...${NC}"
docker-compose up -d --build

# Check status
sleep 3
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo -e "${GREEN}✅ Deploy thành công!${NC}"
    echo ""
    echo -e "📋 Các lệnh hữu ích:"
    echo -e "   ${YELLOW}docker-compose logs -f${NC}      - Xem logs"
    echo -e "   ${YELLOW}docker-compose restart${NC}      - Restart bot"
    echo -e "   ${YELLOW}docker-compose down${NC}         - Dừng bot"
    echo -e "   ${YELLOW}docker-compose up -d --build${NC} - Rebuild & chạy"
    echo ""
else
    echo -e "${RED}❌ Có lỗi khi khởi chạy. Xem logs:${NC}"
    docker-compose logs
    exit 1
fi
