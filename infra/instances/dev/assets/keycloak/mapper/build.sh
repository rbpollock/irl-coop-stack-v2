#!/usr/bin/env bash
# Rebuild coop-groups-mapper.jar (the Keycloak `groups` protocol mapper).
#
# Produces ../coop-groups-mapper.jar, which keycloak.yaml mounts into
# /opt/keycloak/providers/coop-groups-mapper.jar (declarative, survives a
# --force-recreate).
#
# Prereqs: a JDK 21 (Keycloak 25.0.6 runs Java 21) on PATH or JAVA_HOME, and
# the running authentication-keycloak-1 container to source the exact
# 25.0.6 compile classpath from (avoids a Maven/Gradle dependency).
set -euo pipefail
cd "$(dirname "$0")"

KC_IMAGE="authentication-keycloak-1"
JDK="${JAVA_HOME:-}"
JAVAC="${JDK:+$JDK/bin/}javac"
JAR="${JDK:+$JDK/bin/}jar"

# Resolve javac/jar: prefer JAVA_HOME, else PATH.
if ! command -v "$JAVAC" >/dev/null 2>&1; then JAVAC=javac; fi
if ! command -v "$JAR" >/dev/null 2>&1; then JAR=jar; fi

command -v "$JAVAC" >/dev/null 2>&1 || { echo "javac (JDK 21) not found — set JAVA_HOME" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

LIBDIR="$WORK/libs"
mkdir -p "$LIBDIR"
for j in \
  org.keycloak.keycloak-core-25.0.6.jar \
  org.keycloak.keycloak-server-spi-25.0.6.jar \
  org.keycloak.keycloak-server-spi-private-25.0.6.jar \
  org.keycloak.keycloak-services-25.0.6.jar \
  com.fasterxml.jackson.core.jackson-databind-2.17.0.jar \
  com.fasterxml.jackson.core.jackson-core-2.17.0.jar \
  com.fasterxml.jackson.core.jackson-annotations-2.17.0.jar; do
  docker cp "$KC_IMAGE:/opt/keycloak/lib/lib/main/$j" "$LIBDIR/" 2>/dev/null \
    || { echo "failed to copy $j from $KC_IMAGE (is it running?)" >&2; exit 1; }
done
# jboss-logging lives in lib/boot
docker cp "$KC_IMAGE:/opt/keycloak/lib/lib/boot/org.jboss.logging.jboss-logging-3.5.3.Final.jar" "$LIBDIR/" 2>/dev/null

CP="$LIBDIR/org.keycloak.keycloak-core-25.0.6.jar:$LIBDIR/org.keycloak.keycloak-server-spi-25.0.6.jar:$LIBDIR/org.keycloak.keycloak-server-spi-private-25.0.6.jar:$LIBDIR/org.keycloak.keycloak-services-25.0.6.jar:$LIBDIR/com.fasterxml.jackson.core.jackson-databind-2.17.0.jar:$LIBDIR/com.fasterxml.jackson.core.jackson-core-2.17.0.jar:$LIBDIR/com.fasterxml.jackson.core.jackson-annotations-2.17.0.jar:$LIBDIR/org.jboss.logging.jboss-logging-3.5.3.Final.jar"

mkdir -p "$WORK/classes"
"$JAVAC" -classpath "$CP" -d "$WORK/classes" coop/irl/keycloak/CoopGroupsMapper.java

mkdir -p "$WORK/classes/META-INF/services"
cp META-INF/services/org.keycloak.protocol.ProtocolMapper "$WORK/classes/META-INF/services/"
( cd "$WORK/classes" && "$JAR" cf "$OLDPWD/../coop-groups-mapper.jar" . )

echo "built ../coop-groups-mapper.jar"
echo "apply: regenerate (generator.py dev) + docker compose up -d --force-recreate keycloak"
