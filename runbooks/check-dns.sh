#!/usr/bin/env bash
set -e
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then echo "Usage: ./check-dns.sh example.com"; exit 1; fi
echo "== A =="; dig +short A "$DOMAIN"
echo "== AAAA =="; dig +short AAAA "$DOMAIN"
echo "== NS =="; dig +short NS "$DOMAIN"
echo "== CNAME www =="; dig +short CNAME "www.$DOMAIN"
