<?php
// irl.coop webmail — Roundcube + Keycloak OIDC (core OAuth2, since 1.5) + Stalwart XOAUTH2.
// Built into irlcoop/roundcube-oidc:1.6. The entrypoint appends an env-generated
// docker config AFTER this file — DB/IMAP/SMTP/des_key come from the container
// env (roundcube.yaml), OAuth stays here. NOTE: never mention that docker config
// filename in comments — the entrypoint greps for it to decide whether to append
// the include. Dev secrets inline (stack convention); prod should ARG-inject.
$config['plugins'] = array('coop_theme');   // keep the entrypoint's array_merge happy

// --- OAuth2: the fleet session gateway (coop-api issuer at api.irl.coop),
//     client `roundcube` (confidential, S256 PKCE) — the coop_session cookie
//     makes the authorize instant after the dashboard login ---
$config['oauth_provider'] = 'generic';
$config['oauth_provider_name'] = 'irl.coop';
$config['oauth_client_id'] = 'roundcube';
$config['oauth_client_secret'] = '1n41ZsE9nWfmZ8ssOsSjL9lH6XFvtYsz';
$config['oauth_auth_uri'] = 'https://api.irl.coop/api/auth/authorize';
$config['oauth_token_uri'] = 'https://api.irl.coop/api/auth/token';
$config['oauth_identity_uri'] = 'https://api.irl.coop/api/auth/userinfo';
$config['oauth_scope'] = 'openid email profile';
$config['oauth_identity_fields'] = ['email'];
$config['oauth_login_redirect'] = true;   // OAuth-only login (no password form)
$config['oauth_verify_peer'] = true;
$config['oauth_verify_host'] = true;

// --- behind the traefik edge (https) ---
$config['use_https'] = true;
// Allow embedding inside the irl-dashboard (iframe). The default
// 'sameorigin' would refuse framing from irl.coop (different origin).
$config['x_frame_options'] = false;

// --- IMAP/SMTP TLS: self-hosted bridge IP (172.17.0.1) — the *.irl.coop cert
//     can't match the IP, so skip peer verification on the mail legs (dev).
//     Prod: use tls://mail.irl.coop:143/587 and keep verification on.
$config['imap_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];
$config['smtp_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];

// --- misc ---
$config['log_driver'] = 'stdout';
$config['log_max_level'] = 'info';
