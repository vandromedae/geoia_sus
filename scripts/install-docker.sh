#!/usr/bin/env bash
set -euo pipefail

# install-docker.sh — Instala Docker Engine CE via apt (repositório oficial)

GREEN='\033[0;32m'
S='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[ERRO]${NC} $*"; }

# 1. Verificar se já está instalado (docker-ce, não snap)
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>/dev/null || true)
    if echo "$DOCKER_VERSION" | grep -q "Docker version"; then
        # Verificar se é docker-ce (não snap nem docker.io)
        if docker info 2>/dev/null | grep -q "Server Version"; then
            info "Docker já instalado: $DOCKER_VERSION"
            info "Docker Compose: $(docker compose version 2>/dev/null || echo 'não encontrado')"
            echo ""
            echo "Nada a fazer. Para reinstalar, remova primeiro:"
            echo "  sudo apt remove docker-ce docker-ce-cli containerd.io"
            exit 0
        fi
    fi
fi

# 2. Verificar se é root
if [ "$EUID" -eq 0 ]; then
    error "Não rode este script como root."
    error "O script usa sudo quando necessário."
    exit 1
fi

# 3. Detectar conflitos
echo "Verificando conflitos..."

if snap list docker &>/dev/null 2>&1; then
    warn "Docker snap detectado."
    echo "  Remova antes de instalar o Docker Engine CE:"
    echo "    sudo snap remove docker"
    echo ""
    echo "Depois, rode este script novamente."
    exit 1
fi

if dpkg -l | grep -q "^ii.*docker.io " 2>/dev/null; then
    warn "docker.io detectado."
    echo "  Remova antes de instalar o Docker Engine CE:"
    echo "    sudo apt remove docker.io"
    echo ""
    echo "Depois, rode este script novamente."
    exit 1
fi

echo "Sem conflitos. Prosseguindo com a instalação..."

# 4. Instalar dependências
echo ""
echo "Instalando dependências..."
sudo apt update -qq
sudo apt install -y -qq ca-certificates curl gnupg >/dev/null

# 5. Adicionar GPG key oficial do Docker
echo "Adicionando GPG key do Docker..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 6. Adicionar repositório apt
echo "Adicionando repositório apt..."
ARCH=$(dpkg --print-architecture)
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 7. Instalar Docker Engine
echo "Instalando Docker Engine..."
sudo apt update -qq
sudo apt install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null

# 8. Adicionar usuário ao grupo docker
if ! groups "$USER" | grep -q docker; then
    echo "Adicionando $USER ao grupo docker..."
    sudo usermod -aG docker "$USER"
    echo ""
    warn "Faça logout/login ou execute: newgrp docker"
    warn "Para usar Docker sem sudo."
fi

# 9. Verificar instalação
echo ""
echo "=== Verificação ==="
docker --version
docker compose version
echo ""
info "Instalação concluída com sucesso!"
