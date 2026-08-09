# irlcoop/element-web — the official Element Web release tarball + nginx.
# The config.json (homeserver URL, SSO) is mounted at runtime (the stack
# keeps client configs out of the image).
FROM nginx:alpine
ADD https://github.com/element-hq/element-web/releases/download/v1.12.18/element-v1.12.18.tar.gz /tmp/element.tar.gz
RUN tar -xzf /tmp/element.tar.gz -C /usr/share/nginx/html --strip-components=1 \
    && rm /tmp/element.tar.gz \
    && chown -R nginx:nginx /usr/share/nginx/html
