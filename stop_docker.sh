# Precalentar SSH (evita primer timeout)
ssh -o ConnectTimeout=10 -o BatchMode=yes mossa@192.168.1.90 'echo > /dev/null' || true

docker compose down
