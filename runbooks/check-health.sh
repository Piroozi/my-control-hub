#!/usr/bin/env bash
set -e
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then echo "Usage: ./check-health.sh example.com"; exit 1; fi
echo "== HTTP health =="
curl -sS -o /dev/null -w "HTTP %{http_code}\nTime %{time_total}s\nIP %{remote_ip}\n" -L "https://$DOMAIN"
