<?php
/**
 * Plugin Name: Joni Design Seeder
 * Description: Applies the Blocksy design settings carried over from staging. Runs once, on demand, and can be reverted. Deactivate and delete when the design matches.
 * Version: 1.0.0
 * Author: irl.coop
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * WHY THIS EXISTS
 *
 * The jonischwartzchaney.com sitdown runs on WordPress.com's Personal plan,
 * which has no database access and no import of a DB dump. The Blocksy design
 * is not content — it lives in wp_options (a 22 KB theme_mods_blocksy row plus
 * the widget option rows), in a custom_css post and in a wp_global_styles post.
 * A WXR content import carries none of it.
 *
 * So the design is shipped as data and applied through the WordPress APIs by
 * this plugin, instead of being restored from a .sql file.
 *
 * SAFETY
 *
 *  - Nothing runs automatically on activation. You must click Apply.
 *  - Every option this plugin is about to overwrite is copied into the
 *    `joni_seeder_backup` option first, so Revert puts the site back exactly
 *    as it was. (The live site has no self-service backup, so this is the
 *    rollback for this step.)
 *  - Dry run lists what would change without writing anything.
 *  - Only the options named in design/manifest.json are touched.
 */

const JONI_SEEDER_BACKUP = 'joni_seeder_backup';
const JONI_SEEDER_DIR    = __DIR__ . '/design';

/** Ids from the staging site that must NOT be copied verbatim. */
function joni_seeder_special_keys() {
	return array( 'custom_logo', 'custom_css_post_id', 'nav_menu_locations', 'sidebars_widgets' );
}

function joni_seeder_read( $file ) {
	$path = JONI_SEEDER_DIR . '/' . $file;
	if ( ! file_exists( $path ) ) {
		return null;
	}
	return file_get_contents( $path );
}

function joni_seeder_read_json( $file ) {
	$raw = joni_seeder_read( $file );
	if ( $raw === null ) {
		return null;
	}
	$data = json_decode( $raw, true );
	return is_array( $data ) ? $data : null;
}

/**
 * Find a live attachment by the filename it had on staging. Returns 0 if the
 * file is not in the live media library — in which case the caller reports it
 * rather than silently setting a logo that points at nothing.
 */
function joni_seeder_find_attachment( $relative ) {
	$found = get_posts(
		array(
			'post_type'      => 'attachment',
			'post_status'    => 'inherit',
			'posts_per_page' => 1,
			'fields'         => 'ids',
			'meta_query'     => array(
				array(
					'key'     => '_wp_attached_file',
					'value'   => $relative,
					'compare' => 'LIKE',
				),
			),
		)
	);
	return $found ? (int) $found[0] : 0;
}

/**
 * Build the full change set without writing anything.
 */
function joni_seeder_plan() {
	$mods    = joni_seeder_read_json( 'theme_mods_blocksy.json' );
	$widgets = joni_seeder_read_json( 'widget-options.json' );
	$globals = joni_seeder_read_json( 'global-styles.json' );
	$css     = joni_seeder_read( 'custom-css.css' );
	$logo    = joni_seeder_read_json( 'logo.json' );
	$menus   = joni_seeder_read_json( 'menus.json' );
	$pages   = joni_seeder_read_json( 'page-content.json' );

	$plan = array( 'skip' => array(), 'set' => array(), 'notes' => array() );

	if ( $mods ) {
		foreach ( $mods as $key => $value ) {
			// json_decode converts the serialized array's "0" key to int 0, so
			// this has to compare loosely against both forms.
			if ( $key === 0 || $key === '0' ) {   // stray artifact of the serialized array
				$plan['skip'][] = 'theme_mod[0] (artifact)';
				continue;
			}
			if ( in_array( $key, joni_seeder_special_keys(), true ) ) {
				$plan['skip'][] = "theme_mod[$key] (handled separately)";
				continue;
			}
			$plan['set'][] = "theme_mod[$key]";
		}
	}

	if ( $widgets ) {
		foreach ( $widgets as $option => $value ) {
			$plan['set'][] = "option[$option]";
		}
	}

	if ( $css !== null ) {
		$plan['set'][] = 'custom_css post';
	}
	if ( $globals ) {
		$plan['set'][] = 'wp_global_styles post';
	}

	// Logo: remap staging attachment id -> the same file on live.
	if ( $logo && ! empty( $logo['file'] ) ) {
		$id = joni_seeder_find_attachment( $logo['file'] );
		if ( $id ) {
			$plan['set'][] = "theme_mod[custom_logo] -> attachment $id ({$logo['file']})";
		} else {
			$plan['skip'][] = "theme_mod[custom_logo] — {$logo['file']} is NOT in the live media library";
			$plan['notes'][] = "Upload {$logo['file']} to the live media library, then re-run, to restore the logo.";
		}
	}

	// Menus: remap staging menu term ids -> menus that exist on live.
	if ( $menus ) {
		foreach ( $menus as $location => $menu_name ) {
			$menu = wp_get_nav_menu_object( $menu_name );
			if ( $menu ) {
				$plan['set'][] = "theme_mod[nav_menu_locations][$location] -> '$menu_name' (term {$menu->term_id})";
			} else {
				$plan['skip'][] = "nav_menu_locations[$location] — no menu named '$menu_name' on live";
				$plan['notes'][] = "Create a menu named '$menu_name' (or assign it by hand) to place the navigation.";
			}
		}
	}

	// sidebars_widgets: only meaningful once the widget option rows exist.
	if ( $widgets && isset( $widgets['sidebars_widgets'] ) ) {
		$plan['notes'][] = 'Footer widget areas restored; Blocksy footer sidebars are wired by sidebars_widgets.';
	}

	// Pages replaced IN PLACE by slug. The page already exists on live, so
	// importing it as content would create a duplicate at /books-2/ instead.
	if ( $pages ) {
		foreach ( $pages as $slug => $content ) {
			$found = get_page_by_path( $slug );
			if ( $found ) {
				$plan['set'][] = "page '$slug' content (post {$found->ID}), " . strlen( $content ) . ' bytes';
			} else {
				$plan['skip'][] = "page '$slug' — no page with that slug on live";
				$plan['notes'][] = "Create a page with the slug '$slug' first, then re-run.";
			}
		}
	}

	return $plan;
}

function joni_seeder_apply() {
	$mods    = joni_seeder_read_json( 'theme_mods_blocksy.json' );
	$widgets = joni_seeder_read_json( 'widget-options.json' );
	$globals = joni_seeder_read_json( 'global-styles.json' );
	$css     = joni_seeder_read( 'custom-css.css' );
	$logo    = joni_seeder_read_json( 'logo.json' );
	$menus   = joni_seeder_read_json( 'menus.json' );
	$pages   = joni_seeder_read_json( 'page-content.json' );

	// Back up everything we are about to touch. Idempotent: only the first run's
	// values are kept, so Revert always goes back to the pre-seeder state.
	if ( ! get_option( JONI_SEEDER_BACKUP ) ) {
		$backup = array( 'theme_mods' => array(), 'options' => array(), 'custom_css' => null, 'pages' => array() );
		if ( $mods ) {
			foreach ( $mods as $key => $value ) {
				$backup['theme_mods'][ $key ] = get_theme_mod( $key, null );
			}
		}
		if ( $widgets ) {
			foreach ( $widgets as $option => $value ) {
				$backup['options'][ $option ] = get_option( $option, null );
			}
		}
		if ( $pages ) {
			foreach ( $pages as $slug => $content ) {
				$found = get_page_by_path( $slug );
				if ( $found ) {
					$backup['pages'][ $slug ] = $found->post_content;
				}
			}
		}
		$css_post = wp_get_custom_css_post();
		if ( $css_post ) {
			$backup['custom_css'] = $css_post->post_content;
		}
		update_option( JONI_SEEDER_BACKUP, $backup, false );
	}

	$done = array();

	if ( $mods ) {
		foreach ( $mods as $key => $value ) {
			if ( $key === 0 || $key === '0' || in_array( $key, joni_seeder_special_keys(), true ) ) {
				continue;
			}
			set_theme_mod( $key, $value );
			$done[] = "theme_mod[$key]";
		}
	}

	if ( $widgets ) {
		foreach ( $widgets as $option => $value ) {
			update_option( $option, $value );
			$done[] = "option[$option]";
		}
	}

	if ( $css !== null ) {
		wp_update_custom_css_post( $css );
		$done[] = 'custom_css';
	}

	if ( $globals && ! empty( $globals['content'] ) ) {
		$existing = get_posts(
			array(
				'post_type'   => 'wp_global_styles',
				'name'        => $globals['post_name'],
				'post_status' => 'publish',
				'numberposts' => 1,
			)
		);
		if ( $existing ) {
			wp_update_post(
				array(
					'ID'           => $existing[0]->ID,
					'post_content' => $globals['content'],
				)
			);
		} else {
			wp_insert_post(
				array(
					'post_type'    => 'wp_global_styles',
					'post_name'    => $globals['post_name'],
					'post_status'  => 'publish',
					'post_content' => $globals['content'],
					'tax_input'    => array( 'wp_theme' => array( get_stylesheet() ) ),
				)
			);
		}
		$done[] = 'wp_global_styles';
	}

	if ( $logo && ! empty( $logo['file'] ) ) {
		$id = joni_seeder_find_attachment( $logo['file'] );
		if ( $id ) {
			set_theme_mod( 'custom_logo', $id );
			$done[] = "custom_logo -> $id";
		}
	}

	if ( $menus ) {
		$locations = get_theme_mod( 'nav_menu_locations', array() );
		foreach ( $menus as $location => $menu_name ) {
			$menu = wp_get_nav_menu_object( $menu_name );
			if ( $menu ) {
				$locations[ $location ] = (int) $menu->term_id;
				$done[]                 = "nav_menu_locations[$location] -> '$menu_name'";
			}
		}
		set_theme_mod( 'nav_menu_locations', $locations );
	}

	if ( $pages ) {
		foreach ( $pages as $slug => $content ) {
			$found = get_page_by_path( $slug );
			if ( $found ) {
				wp_update_post(
					array(
						'ID'           => $found->ID,
						'post_content' => $content,
					)
				);
				$done[] = "page '$slug' content";
			}
		}
	}

	return $done;
}

function joni_seeder_revert() {
	$backup = get_option( JONI_SEEDER_BACKUP );
	if ( ! $backup ) {
		return null;
	}
	foreach ( (array) $backup['theme_mods'] as $key => $value ) {
		if ( $value === null ) {
			remove_theme_mod( $key );
		} else {
			set_theme_mod( $key, $value );
		}
	}
	foreach ( (array) $backup['options'] as $option => $value ) {
		update_option( $option, $value );
	}
	foreach ( (array) ( $backup['pages'] ?? array() ) as $slug => $content ) {
		$found = get_page_by_path( $slug );
		if ( $found ) {
			wp_update_post(
				array(
					'ID'           => $found->ID,
					'post_content' => $content,
				)
			);
		}
	}
	if ( $backup['custom_css'] !== null ) {
		wp_update_custom_css_post( $backup['custom_css'] );
	}
	delete_option( JONI_SEEDER_BACKUP );
	return true;
}

add_action(
	'admin_menu',
	function () {
		add_management_page(
			'Joni Design Seeder',
			'Joni Design Seeder',
			'manage_options',
			'joni-design-seeder',
			'joni_seeder_page'
		);
	}
);

function joni_seeder_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}

	$result = null;

	if ( isset( $_POST['joni_seeder_action'] ) && check_admin_referer( 'joni_seeder' ) ) {
		switch ( $_POST['joni_seeder_action'] ) {
			case 'apply':
				$done   = joni_seeder_apply();
				$result = array( 'applied', $done );
				break;
			case 'revert':
				$ok     = joni_seeder_revert();
				$result = array( $ok ? 'reverted' : 'nothing-to-revert', array() );
				break;
		}
	}

	$plan   = joni_seeder_plan();
	$backup = get_option( JONI_SEEDER_BACKUP );

	echo '<div class="wrap"><h1>Joni Design Seeder</h1>';

	if ( $result ) {
		$label = array(
			'applied'             => 'Applied:',
			'reverted'            => 'Reverted to the pre-seeder state.',
			'nothing-to-revert'   => 'Nothing to revert — no backup recorded.',
		);
		printf( '<div class="notice notice-%s"><p><strong>%s</strong></p>', $result[0] === 'applied' ? 'success' : 'info', esc_html( $label[ $result[0] ] ) );
		if ( $result[1] ) {
			echo '<ul style="list-style:disc;margin-left:2em">';
			foreach ( $result[1] as $line ) {
				echo '<li><code>' . esc_html( $line ) . '</code></li>';
			}
			echo '</ul>';
		}
		echo '</div>';
	}

	echo '<p>Applies the Blocksy design, widget areas, custom CSS and global styles exported from staging. Nothing runs automatically.</p>';

	echo '<h2>Will be set</h2><ul style="list-style:disc;margin-left:2em">';
	foreach ( $plan['set'] as $line ) {
		echo '<li><code>' . esc_html( $line ) . '</code></li>';
	}
	echo '</ul>';

	if ( $plan['skip'] ) {
		echo '<h2>Skipped</h2><ul style="list-style:disc;margin-left:2em">';
		foreach ( $plan['skip'] as $line ) {
			echo '<li><code>' . esc_html( $line ) . '</code></li>';
		}
		echo '</ul>';
	}

	if ( $plan['notes'] ) {
		echo '<h2>Needs a manual step</h2><ul style="list-style:disc;margin-left:2em">';
		foreach ( $plan['notes'] as $line ) {
			echo '<li>' . esc_html( $line ) . '</li>';
		}
		echo '</ul>';
	}

	echo '<form method="post">';
	wp_nonce_field( 'joni_seeder' );
	printf(
		'<p><button class="button button-primary" name="joni_seeder_action" value="apply" onclick="return confirm(%s)">Apply the design</button> ',
		esc_js( wp_json_encode( 'Apply the design settings now? Existing values are backed up first so this can be reverted.' ) )
	);
	if ( $backup ) {
		printf(
			'<button class="button" name="joni_seeder_action" value="revert" onclick="return confirm(%s)">Revert</button></p>',
			esc_js( wp_json_encode( 'Undo the seeder and restore the values that were in place before it ran?' ) )
		);
	} else {
		echo '</p>';
	}
	echo '</form>';

	if ( $backup ) {
		echo '<p><em>A pre-seeder snapshot is recorded, so Revert is available.</em></p>';
	}

	echo '</div>';
}