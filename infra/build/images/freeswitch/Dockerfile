# FreeSWITCH — source-compiled (spike). Layer FusionPBX (PHP+nginx) on top once
# mod_sofia WSS is proven. Single stage: build tools stay in the image for now,
# which is fine for a feasibility probe; refactor to multi-stage before prod.
FROM debian:12

ENV DEBIAN_FRONTEND=noninteractive

# Build deps for FreeSWITCH 1.10 on Debian 12 (bookworm).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool libtool-bin pkg-config cmake nasm \
    git wget ca-certificates \
    libncurses-dev libssl-dev libcurl4-openssl-dev libjpeg-dev libsqlite3-dev \
    libspeex-dev libspeexdsp-dev libldns-dev libedit-dev libpq-dev liblua5.1-0-dev \
    lua-sql-postgres \
    libwebsockets-dev libspandsp-dev libxml2-dev libpcre3-dev zlib1g-dev \
    libavformat-dev libswscale-dev libavutil-dev libavcodec-dev libvpx-dev libopus-dev \
    libsndfile1-dev libyuv-dev uuid-dev \
  && rm -rf /var/lib/apt/lists/*

# libks — FreeSWITCH 1.10 dependency (cmake).
RUN git clone -b v2.0.9 https://github.com/signalwire/libks.git /usr/src/libks \
  && cd /usr/src/libks && cmake . && make -j"$(nproc)" && make install && ldconfig

# spandsp3 — required by FreeSWITCH 1.10.7+ (Debian's libspandsp-dev is 0.0.6, too old).
RUN git clone -b v3.1.1 https://github.com/freeswitch/spandsp.git /usr/src/spandsp \
  && cd /usr/src/spandsp \
  && ./bootstrap.sh \
  && ./configure --prefix=/usr \
  && make -j"$(nproc)" \
  && make install \
  && ldconfig

# sofia-sip — required by FreeSWITCH 1.10.7+ (>=1.13.17; the FS fork carries WSS/RFC7118).
RUN git clone -b v1.13.18 https://github.com/freeswitch/sofia-sip.git /usr/src/sofia-sip \
  && cd /usr/src/sofia-sip \
  && ./bootstrap.sh \
  && ./configure --prefix=/usr \
  && make -j"$(nproc)" \
  && make install \
  && ldconfig

# FreeSWITCH 1.10 (latest stable release tag). Minimal module set for the spike
# (sofia + event_socket + dialplan + conference + core); omits language/LDAP/
# cache modules so lua/python/perl/java/yaml dev packages aren't required.
# EXCEPTIONS (added back onto the minimal set):
#   languages/mod_lua — FusionPBX 5.5.x serves directory/dialplan/configuration
#     XML through mod_lua's xml_handler (lua.conf.xml: xml-handler-script =
#     app.lua xml_handler), NOT mod_xml_curl.
#   codecs/mod_opus — WebRTC audio: browsers offer OPUS (the one mandatory
#     codec). SRTP/DTLS is already covered by the bundled libs/srtp, so mod_opus
#     is the only codec module a real in-browser call needs (G.711 is native).
RUN git clone --depth 1 -b v1.10.12 https://github.com/signalwire/freeswitch.git /usr/src/freeswitch \
  && cd /usr/src/freeswitch \
  && cp conf/minimal/modules.conf modules.conf \
  && printf 'languages/mod_lua\n' >> modules.conf \
  && printf 'codecs/mod_opus\n' >> modules.conf \
  && ./bootstrap.sh -j \
  && ./configure \
  && make -j"$(nproc)" \
  && make install \
  && make cd-sounds-install cd-moh-install

# SIP (5060), external (5080), event socket (8021), WSS (7443), HTTP (for verto/status).
EXPOSE 5060/tcp 5060/udp 5080/tcp 5080/udp 8021 7443 8080

# Entrypoint combines the mounted wildcard cert -> wss.pem, then runs FreeSWITCH
# in the foreground (-nf = no fork; required for Docker to keep PID 1 alive).
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["-nonat", "-nf"]
