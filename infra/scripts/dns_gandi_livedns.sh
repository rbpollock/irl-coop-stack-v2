#!/bin/sh
# dns_gandi_livedns hook for acme.sh — irl.coop apex zone (subdomain wildcards
# like *.studio.irl.coop share the same zone). Gandi LiveDNS v5 API:
#   PUT    /v5/livedns/domains/<zone>/records/<name>/TXT  -> 201
#   DELETE /v5/livedns/domains/<zone>/records/<name>/TXT  -> 204
# Auth: Bearer $GANDI_LIVEDNS_KEY (the 40-char v5 API key).
# The ZONE is the apex (default `irl.coop`, override with GANDI_ZONE); the
# record name is the challenge FQDN relative to that zone:
#   _acme-challenge.irl.coop        -> _acme-challenge
#   _acme-challenge.studio.irl.coop -> _acme-challenge.studio
# add() MERGES into an existing TXT rrset so apex + subdomain challenges coexist.
GANDI_BASE="https://api.gandi.net/v5/livedns"
ZONE="${GANDI_ZONE:-irl.coop}"

# _acme-challenge.studio.irl.coop -> _acme-challenge.studio (relative to ZONE)
_gandi_name() {
  echo "${1%.$ZONE}"
}

_gandi_url() {
  echo "$GANDI_BASE/domains/$ZONE/records/$(_gandi_name "$1")/TXT"
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
  code="$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$url" \
    -H "Authorization: Bearer $GANDI_LIVEDNS_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_ttl\":300,\"rrset_values\":$new_values}")"
  [ "$code" = "201" ] || [ "$code" = "200" ]
}

dns_gandi_livedns_rm() {
  fulldomain="$1"
  url="$(_gandi_url "$fulldomain")"
  # DELETE returns 204 with an EMPTY body — accept that as success
  resp="$(curl -s -w '\n%{http_code}' -X DELETE "$url" -H "Authorization: Bearer $GANDI_LIVEDNS_KEY")"
  code="$(echo "$resp" | tail -1)"
  [ "$code" = "204" ] || [ "$code" = "200" ] || echo "$resp" | grep -q '"message"'
}
