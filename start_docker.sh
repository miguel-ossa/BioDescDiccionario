export FLYCTL_INSTALL="/Users/mossa/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_BASE_URL=http://localhost:11434

docker compose up --build
