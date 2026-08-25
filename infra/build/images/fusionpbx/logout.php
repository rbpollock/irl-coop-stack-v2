<?php
/*
	Global logout for the FusionPBX ops UI.

	FusionPBX's own session is just one of three: PHPSESSID (this app),
	_oauth2_proxy (the gate), and coop_session (the fleet master). Logging out
	here clears PHPSESSID, then hands off to the gate's /oauth2/sign_out, which
	clears _oauth2_proxy and redirects to the coop logout
	(https://api.irl.coop/api/auth/logout) to clear coop_session — landing on the
	dashboard. Net effect: one click logs you out of the whole coop.
*/
require_once __DIR__ . "/resources/require.php";
session_unset();
session_destroy();
header("Location: /oauth2/sign_out?rd=" . urlencode("https://api.irl.coop/api/auth/logout"));
exit;
