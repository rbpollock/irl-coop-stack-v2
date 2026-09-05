# irlcoop/cinny — the Cinny Matrix client (chat + video calling), built from
# source so we can carry the irl.coop auto-login patch (auto-redirect to SSO
# when unauthenticated, so members logged into the dashboard land in Cinny
# with no click). The config.json (homeserver, hash router) is mounted at
# runtime from the instance tree.

FROM node:22-alpine AS build
RUN apk add --no-cache git
RUN git clone --depth 1 --branch v4.12.6 https://github.com/cinnyapp/cinny.git /src
WORKDIR /src
COPY apply-patch.mjs /tmp/apply-patch.mjs
RUN node /tmp/apply-patch.mjs
RUN npm install --no-audit --no-fund && npm run build

FROM nginx:alpine
COPY default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html
