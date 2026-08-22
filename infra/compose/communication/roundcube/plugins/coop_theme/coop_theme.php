<?php
/**
 * coop_theme — apply the member's shared accent theme from coop-api.
 *
 * Reads `preferences.theme` from the coop profile (GET /api/v1/profile) and
 * adds a `theme-<name>` class to <html>. The shadcn-mail skin's CSS variables
 * (--primary / --ring) recolor the accent to match the dashboard's theme
 * picker, so "one identity, every app" includes the chosen accent color.
 *
 * The coop JWT (the OAuth access_token) is stripped from the session by
 * Roundcube's OAuth core and stored encrypted in $_SESSION['password'] as
 * "Bearer <jwt>" — we decrypt it here to call coop-api.
 *
 * Enabled via $config['plugins'][] = 'coop_theme'.
 */
class coop_theme extends rcube_plugin
{
    public $task = 'login|mail|settings|addressbook|.*';

    private const PROFILE_URL = 'https://api.irl.coop/api/v1/profile';
    private const THEMES = ['zinc', 'slate', 'stone', 'gray', 'neutral', 'red', 'rose', 'orange', 'green', 'blue', 'yellow', 'violet'];

    public function init()
    {
        $this->add_hook('startup', [$this, 'on_startup']);
    }

    public function on_startup($args)
    {
        $rcmail = rcmail::get_instance();

        // The coop JWT lives in $_SESSION['password'] as "Bearer <jwt>".
        $auth = $rcmail->decrypt($_SESSION['password'] ?? '');
        $token = trim((string) preg_replace('/^[A-Za-z-]+\s+/', '', (string) $auth));
        if (!$token) {
            return $args;
        }

        // One fetch per session (the theme only changes when the member edits it).
        if (array_key_exists('coop_theme', $_SESSION)) {
            $theme = $_SESSION['coop_theme'];
        } else {
            $theme = $this->fetch_theme($token);
            $_SESSION['coop_theme'] = $theme;
        }

        if (!$theme) {
            return $args;
        }

        // Inject the theme class on <html>. Only on HTML output: AJAX requests
        // (refresh/list/getunread) use rcmail_output_json, which has no
        // add_script method — and the class only needs setting once per page
        // render, not on every polling request.
        if (method_exists($rcmail->output, 'add_script')) {
            $rcmail->output->add_script(
                'document.documentElement.classList.add(' . json_encode('theme-' . $theme) . ');',
                'head_top'
            );
        }

        return $args;
    }

    private function fetch_theme($token)
    {
        $ch = curl_init(self::PROFILE_URL);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $token],
            CURLOPT_TIMEOUT => 5,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $body = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if (!$body || $code !== 200) {
            return null;
        }

        $data = json_decode($body, true);
        $theme = $data['preferences']['theme'] ?? null;

        return is_string($theme) && in_array($theme, self::THEMES, true) ? $theme : null;
    }
}
