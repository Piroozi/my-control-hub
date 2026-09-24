#!/usr/bin/env bash
set -e
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then echo "Set CLOUDFLARE_API_TOKEN first."; exit 1; fi
curl -sS "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json"
echo
