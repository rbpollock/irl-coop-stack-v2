# irlcoop/element-web — the official Element Web release tarball + nginx.
# The config.json (homeserver URL, SSO) is mounted at runtime (the stack
# keeps client configs out of the image).
#
# irl.coop: the mobile redirect is HARDCODED in the app entry (apps/web/src/
# vector/index.ts) — on any iOS/Android user-agent it jumps to mobile_guide/
# before the config even loads, and it cannot be disabled via config.json.
# We neutralise it by pre-setting the same sessionStorage flag the mobile-guide
# page's "continue in browser" sets, via a same-origin script loaded in <head>
# (the CSP allows 'self', not inline — hence a separate .js file).
FROM nginx:alpine
ADD https://github.com/element-hq/element-web/releases/download/v1.12.18/element-v1.12.18.tar.gz /tmp/element.tar.gz
RUN tar -xzf /tmp/element.tar.gz -C /usr/share/nginx/html --strip-components=1 \
    && rm /tmp/element.tar.gz \
    && chown -R nginx:nginx /usr/share/nginx/html \
    && echo 'document.cookie="element_mobile_redirect_to_guide=false;path=/;max-age=14400";sessionStorage.setItem("skip_mobile_redirect","true");' > /usr/share/nginx/html/skip-mobile.js \
    && sed -i 's#<head>#<head><script src="skip-mobile.js"></script>#' /usr/share/nginx/html/index.html
