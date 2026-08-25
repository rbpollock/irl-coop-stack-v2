<?php
/*
	Header SSO for the FusionPBX ops UI.

	The pbx route is fronted by oauth2-proxy (--allowed-group=telephony.platform.admin),
	so by the time a request reaches this file the caller is already a platform
	admin. In PROXY mode oauth2-proxy forwards the identity as X-Forwarded-Email
	(pass-user-headers, default on); X-Auth-Request-Email is the auth_request-mode
	variant. This header is trustworthy ONLY because FusionPBX's nginx is reachable
	exclusively through the gate (no host port, no direct edge route).

	This shim maps the gate identity to an EXISTING FusionPBX user (username = the
	coop email, or user_email = email) and establishes the PHP session without a
	password. It deliberately does NOT create users: user creation (bcrypt hash +
	group assignment) is a one-time operator step in the FusionPBX UI. An identity
	with no matching v_users row falls through to the normal password login.
*/

$sso_email = '';
if (!empty($_SERVER['HTTP_X_AUTH_REQUEST_EMAIL'])) {
	$sso_email = $_SERVER['HTTP_X_AUTH_REQUEST_EMAIL'];
} elseif (!empty($_SERVER['HTTP_X_FORWARDED_EMAIL'])) {
	$sso_email = $_SERVER['HTTP_X_FORWARDED_EMAIL'];
}

if (!empty($sso_email)) {

	// Only bootstrap when the session hasn't started yet (every request arrives
	// here before the page's own require.php does session_start()).
	if (session_status() === PHP_SESSION_NONE) {
		$require = '/var/www/fusionpbx/resources/require.php';
		if (is_file($require)) {
			// require_once: the page's own require.php is then a no-op.
			require_once $require;
		}
		if (session_status() === PHP_SESSION_NONE) {
			return;
		}
	}

	// Already authenticated (subsequent requests carry the session cookie).
	if (!empty($_SESSION['authorized'])) {
		return;
	}

	global $database;
	if (!isset($database)) {
		return;
	}

	$email = $sso_email;

	// Single-domain install: the coop is one FusionPBX domain.
	$domain = $database->select(
		"select domain_uuid, domain_name from v_domains order by domain_name asc limit 1",
		null, 'row'
	);

	if (!empty($domain['domain_uuid']) && is_uuid($domain['domain_uuid'])) {
		$user = $database->select(
			"select user_uuid, username from v_users
			  where domain_uuid = :domain_uuid
			    and (username = :u1 or user_email = :u2)
			  limit 1",
			['domain_uuid' => $domain['domain_uuid'], 'u1' => $email, 'u2' => $email],
			'row'
		);

		if (!empty($user['user_uuid']) && is_uuid($user['user_uuid'])) {
			// create_user_session reads $settings (time zone etc.), so pass a
			// settings object scoped to this domain/user — mirroring what
			// authentication::validate() does on a normal login.
			$settings = new settings([
				'database'   => $database,
				'domain_uuid' => $domain['domain_uuid'],
				'user_uuid'   => $user['user_uuid'],
			]);
			authentication::create_user_session([
				'domain_uuid' => $domain['domain_uuid'],
				'domain_name' => $domain['domain_name'],
				'user_uuid'   => $user['user_uuid'],
				'username'    => $user['username'],
			], $settings);
			$_SESSION['authorized'] = true;
		} else {
			// No mapping for this identity — fall through to the password login.
			openlog('FusionPBX', LOG_NDELAY, LOG_AUTH);
			syslog(LOG_WARNING, "[header-sso] no v_users mapping for " . $email . " — falling back to password login");
			closelog();
		}
	}
}
