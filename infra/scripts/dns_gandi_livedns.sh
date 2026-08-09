#!/bin/sh
# Working dns_gandi_livedns hook for acme.sh — replaces the image's (which
# fails on the current LiveDNS v5 API). Verified against api.gandi.net/v5:
#   PUT    /v5/livedns/domains/<zone>/records/_acme-challenge/TXT  -> 201
#   DELETE /v5/livedns/domains/<zone>/records/_acme-challenge/TXT  -> 204
# Auth: Bearer $GANDI_LIVEDNS_KEY (the 40-char v5 API key).
# Both the wildcard and the apex challenge land on _acme-challenge.<zone>, so
# add() MERGES into the existing TXT record instead of replacing it.
GANDI_BASE="https://api.gandi.net/v5/livedns"

_gandi_zone() {
  echo "$1" | sed 's/^_acme-challenge\.//'
}

_gandi_url() {
  echo "$GANDI_BASE/domains/$(_gandi_zone "$1")/records/_acme-challenge/TXT"
}

dns_gandi_livedns_add() {
  fulldomain="$1"
  txtvalue="$2"
  url="$(_gandi_url "$fulldomain")"
  existing="$(curl -s -H "Authorization: Bearer $GANDI_LIVEDNS_KEY" "$url")"
  values="$(echo "$existing" | sed -n 's/.*"rrset_values":\(\[[^]]*\]\).*/\1/p')"
  if [ -n "$values" ] && [ "$values" != "null" ]; then
    new_values="$(echo "$values" | sed "s/\]$/, \"$txtvalue\"]/")"
  else
    new_values="[\"$txtvalue\"]"
  fi
  curl -s -X PUT "$url" \
    -H "Authorization: Bearer $GANDI_LIVEDNS_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_ttl\":300,\"rrset_values\":$new_values}" \
    | grep -q '"message"' && return 0
  return 1
}

dns_gandi_livedns_rm() {
  fulldomain="$1"
  url="$(_gandi_url "$fulldomain")"
  # DELETE returns 204 with an EMPTY body — accept that as success
  resp="$(curl -s -w '\n%{http_code}' -X DELETE "$url" -H "Authorization: Bearer $GANDI_LIVEDNS_KEY")"
  code="$(echo "$resp" | tail -1)"
  [ "$code" = "204" ] || [ "$code" = "200" ] || echo "$resp" | grep -q '"message"'
}
