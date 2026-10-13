<?php
/**
 * Plugin Name: Joni Site Installer
 * Description: One-click migration of the jonischwartzchaney.com redesign from staging. Upload, activate, Tools -> Joni Site Installer -> Run all.
 * Version: 1.0.0
 * Author: irl.coop
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * WHY THIS IS A PLUGIN AND NOT A SCRIPT
 *
 * The destination is WordPress.com on the Personal plan: no SSH, no SFTP, no
 * WP-CLI, no database access. So the only code that can run on the target is
 * code that arrives as a plugin. This installs everything else — theme, plugins,
 * content, uploads, and the Blocksy design that lives in wp_options — using
 * WordPress's own APIs, from the wp-admin side.
 *
 * Everything is IDEMPOTENT: every step checks the current state first and can be
 * re-run safely. Steps run one per AJAX request so no single request can hit a
 * PHP time limit, and a run that dies halfway resumes from where it stopped.
 */

const JONI_INSTALLER_SNAPSHOT = 'joni_installer_snapshot';
const JONI_INSTALLER_CREATED  = 'joni_installer_created';
const JONI_INSTALLER_PAYLOAD  = __DIR__ . '/payload';

function joni_payload() {
	static $cache = null;
	if ( $cache !== null ) {
		return $cache;
	}
	$raw   = @file_get_contents( JONI_INSTALLER_PAYLOAD . '/site.json' );
	$cache = $raw ? json_decode( $raw, true ) : array();
	return is_array( $cache ) ? $cache : array();
}

function joni_step_list() {
	return array(
		'theme'      => 'Install the Blocksy theme',
		'plugins'    => 'Install Blocksy Companion + Stackable',
		'joni-books' => 'Install the joni-books plugin',
		'media'      => 'Place the images the redesign needs',
		'content'    => 'Create the new pages, events and book entries',
		'categories' => 'Put the existing posts into News / Reviews / Events',
		'menus'      => 'Build the navigation menu',
		'design'     => 'Apply the Blocksy design',
		'finish'     => 'Activate the theme and set the homepage',
	);
}

/** Capture the HTML that the upgrader skins print on success. */
function joni_quiet( callable $fn ) {
	ob_start();
	try {
		$r = $fn();
	} finally {
		$out = ob_get_clean();
	}
	return array( $r, $out );
}

// --------------------------------------------------------------------- steps

function joni_step_theme() {
	$slug = joni_payload()['settings']['theme'] ?? 'blocksy';
	$log  = array();

	if ( wp_get_theme( $slug )->exists() ) {
		return array( 'log' => array( "theme '$slug' already installed" ) );
	}

	require_once ABSPATH . 'wp-admin/includes/theme.php';
	require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
	$api = themes_api( 'theme_information', array( 'slug' => $slug ) );
	if ( is_wp_error( $api ) ) {
		return array( 'error' => 'themes_api: ' . $api->get_error_message() );
	}
	$upgrader = new Theme_Upgrader( new Automatic_Upgrader_Skin() );
	list( $res ) = joni_quiet( function () use ( $upgrader, $api ) {
		return $upgrader->install( $api->download_link );
	} );
	if ( is_wp_error( $res ) ) {
		return array( 'error' => 'install: ' . $res->get_error_message() );
	}
	if ( ! wp_get_theme( $slug )->exists() ) {
		return array( 'error' => "theme '$slug' still missing after install" );
	}
	return array( 'log' => array( "installed theme '$slug'" ) );
}

function joni_step_plugins() {
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
	require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
	require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';

	$log = array();
	foreach ( (array) ( joni_payload()['settings']['plugins'] ?? array() ) as $slug ) {
		if ( ! joni_plugin_file( $slug ) ) {
			$api = plugins_api( 'plugin_information', array( 'slug' => $slug, 'fields' => array( 'sections' => false ) ) );
			if ( is_wp_error( $api ) ) {
				return array( 'error' => "plugins_api($slug): " . $api->get_error_message() );
			}
			$upgrader = new Plugin_Upgrader( new Automatic_Upgrader_Skin() );
			list( $res ) = joni_quiet( function () use ( $upgrader, $api ) {
				return $upgrader->install( $api->download_link );
			} );
			if ( is_wp_error( $res ) ) {
				return array( 'error' => "install($slug): " . $res->get_error_message() );
			}
			$log[] = "installed $slug";
		} else {
			$log[] = "$slug already present";
		}

		// Resolve the plugin's real main file. It is NOT always
		// <slug>/<slug>.php — Stackable's is stackable-ultimate-gutenberg-blocks/plugin.php,
		// and assuming otherwise makes activation fail with "Plugin file does not exist".
		$file = joni_plugin_file( $slug );
		if ( ! $file ) {
			return array( 'error' => "$slug: no plugin file found after install" );
		}

		list( $r ) = joni_quiet( function () use ( $file ) {
			return activate_plugin( $file );
		} );
		if ( is_wp_error( $r ) ) {
			return array( 'error' => "activate($slug): " . $r->get_error_message() );
		}
		$log[] = ( is_plugin_active( $file ) ? 'active: ' : 'NOT ACTIVE: ' ) . "$slug ($file)";
	}
	return array( 'log' => $log );
}

/** The main plugin file for a directory slug, from the plugin headers. */
function joni_plugin_file( $slug ) {
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
	if ( file_exists( WP_PLUGIN_DIR . '/' . $slug . '/' . $slug . '.php' ) ) {
		return $slug . '/' . $slug . '.php';
	}
	foreach ( get_plugins() as $file => $data ) {
		if ( strpos( $file, $slug . '/' ) === 0 ) {
			return $file;
		}
	}
	return null;
}

function joni_step_joni_books() {
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
	require_once ABSPATH . 'wp-admin/includes/file.php';

	$dir  = WP_PLUGIN_DIR . '/joni-books';
	$file = 'joni-books/joni-books.php';
	$src  = JONI_INSTALLER_PAYLOAD . '/joni-books';
	$zip  = JONI_INSTALLER_PAYLOAD . '/joni-books.zip';
	$log  = array();

	$installed = $dir . '/joni-books.php';
	$bundled   = $src . '/joni-books.php';

	// Replace when the installed copy differs from the bundled one. Without this
	// a site that already has an older joni-books keeps it forever and the fix
	// never arrives — "already present" is not the same as "up to date".
	$needs = ! file_exists( $installed )
		|| ( file_exists( $bundled ) && md5_file( $installed ) !== md5_file( $bundled ) );

	if ( ! $needs ) {
		$log[] = 'joni-books already present and up to date';
	} else {
		$log[] = file_exists( $installed )
			? 'joni-books on this site differs from the bundled copy — replacing it'
			: 'joni-books is not installed yet';
		// Three ways to place it, cheapest machinery first. The plugin upgrader is
		// deliberately LAST: it needs a writable wp-content/upgrade, and on a
		// locked-down host it can raise a fatal — which would end the request
		// before any fallback had a chance to run.
		$tried  = array();
		$placed = false;

		if ( is_dir( $src ) ) {
			$r = joni_copy_dir( $src, $dir );
			if ( true === $r ) {
				$placed = true;
				$log[]  = 'placed by direct file copy';
			} else {
				$tried[] = 'direct copy: ' . ( is_wp_error( $r ) ? $r->get_error_message() : 'unknown failure' );
			}
		} else {
			$tried[] = "direct copy: no bundled payload/joni-books directory";
		}

		if ( ! $placed && file_exists( $zip ) ) {
			list( $r ) = joni_quiet( function () use ( $zip ) {
				return unzip_file( $zip, WP_PLUGIN_DIR );
			} );
			if ( is_wp_error( $r ) ) {
				$tried[] = 'unzip_file: ' . $r->get_error_message();
			} elseif ( ! file_exists( $dir . '/joni-books.php' ) ) {
				$tried[] = 'unzip_file: reported success but the plugin file is not there';
			} else {
				$placed = true;
				$log[]  = 'placed by unzip_file';
			}
		}

		if ( ! $placed && file_exists( $zip ) ) {
			require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
			$upgrader  = new Plugin_Upgrader( new Automatic_Upgrader_Skin() );
			list( $r ) = joni_quiet( function () use ( $upgrader, $zip ) {
				return $upgrader->install( $zip );
			} );
			if ( is_wp_error( $r ) ) {
				$tried[] = 'plugin upgrader: ' . $r->get_error_message();
			} elseif ( ! file_exists( $dir . '/joni-books.php' ) ) {
				$tried[] = 'plugin upgrader: reported success but the plugin file is not there';
			} else {
				$placed = true;
				$log[]  = 'placed by the plugin upgrader';
			}
		}

		if ( ! $placed ) {
			return array(
				'error' => 'could not place joni-books — ' . implode( ' | ', $tried )
					. '. wp-content/plugins writable: ' . ( wp_is_writable( WP_PLUGIN_DIR ) ? 'yes' : 'no' ),
				'log'   => $log,
			);
		}
	}

	joni_quiet( function () use ( $file ) {
		return activate_plugin( $file );
	} );
	if ( ! is_plugin_active( $file ) ) {
		return array( 'error' => 'joni-books is installed but did not activate', 'log' => $log );
	}
	$log[] = ( file_exists( $dir . '/joni-books.php' ) ? 'installed: ' : 'MISSING: ' ) . 'joni-books/joni-books.php';
	$log[] = 'active: joni-books';

	// The book post type is registered during plugins_loaded, which has ALREADY
	// run by the time this handler executes — so on the request that activates the
	// plugin it cannot be present yet, however successful the install was. An
	// earlier version treated that as a hard failure and reported an error on a
	// perfectly good install.
	$log[] = post_type_exists( 'book' )
		? "post type 'book' is registered"
		: "post type 'book' registers on the next request (expected right after activation)";

	return array( 'log' => $log );
}

/**
 * Copy a directory tree with plain PHP filesystem calls.
 *
 * Deliberately avoids the WP_Filesystem abstraction and the upgrader: this is the
 * path that has to work when the host's own filesystem layer is the thing that is
 * unavailable.
 */
function joni_copy_dir( $from, $to ) {
	if ( ! wp_mkdir_p( $to ) ) {
		return new WP_Error( 'joni_mkdir', "could not create $to" );
	}
	if ( ! is_readable( $from ) ) {
		return new WP_Error( 'joni_read', "$from is not readable" );
	}
	$copied = 0;
	$items  = new RecursiveIteratorIterator(
		new RecursiveDirectoryIterator( $from, FilesystemIterator::SKIP_DOTS ),
		RecursiveIteratorIterator::SELF_FIRST
	);
	foreach ( $items as $item ) {
		$target = $to . '/' . $items->getSubPathname();
		if ( $item->isDir() ) {
			if ( ! wp_mkdir_p( $target ) ) {
				return new WP_Error( 'joni_mkdir', "could not create $target" );
			}
			continue;
		}
		if ( ! copy( $item->getPathname(), $target ) ) {
			return new WP_Error( 'joni_copy', "could not write $target" );
		}
		$copied++;
	}
	return $copied > 0 ? true : new WP_Error( 'joni_empty', "no files found under $from" );
}

/** Find an attachment whose stored file path ends with the given basename. */
function joni_find_attachment_by_basename( $basename ) {
	global $wpdb;
	$id = $wpdb->get_var( $wpdb->prepare(
		"SELECT post_id FROM {$wpdb->postmeta} WHERE meta_key='_wp_attached_file' AND meta_value LIKE %s LIMIT 1",
		'%' . $wpdb->esc_like( $basename )
	) );
	return $id ? (int) $id : 0;
}

/** Insert a file at an exact path under uploads, preserving the original folder. */
function joni_place_attachment( $rel, $source ) {
	$uploads = wp_upload_dir();
	$target  = trailingslashit( $uploads['basedir'] ) . $rel;
	if ( ! file_exists( dirname( $target ) ) ) {
		wp_mkdir_p( dirname( $target ) );
	}
	if ( ! @copy( $source, $target ) ) {
		return 0;
	}
	$type = wp_check_filetype( basename( $target ) );
	$id   = wp_insert_attachment(
		array(
			'post_mime_type' => $type['type'] ?: 'application/octet-stream',
			'post_title'     => preg_replace( '/\.[^.]+$/', '', basename( $rel ) ),
			'post_status'    => 'inherit',
			'guid'           => trailingslashit( $uploads['baseurl'] ) . $rel,
		),
		$target
	);
	if ( is_wp_error( $id ) || ! $id ) {
		return 0;
	}
	require_once ABSPATH . 'wp-admin/includes/image.php';
	update_post_meta( $id, '_wp_attached_file', $rel );
	wp_update_attachment_metadata( $id, wp_generate_attachment_metadata( $id, $target ) );
	return (int) $id;
}

/**
 * Every image the payload references, as basename => original relative path.
 * Returns basename => attachment id, uploading any that are not on this site.
 */
function joni_ensure_media() {
	$map = array();
	foreach ( (array) ( joni_payload()['media'] ?? array() ) as $rel ) {
		$base = basename( $rel );
		$id   = joni_find_attachment_by_basename( $base );
		if ( ! $id ) {
			$src = JONI_INSTALLER_PAYLOAD . '/media/' . $base;
			if ( file_exists( $src ) ) {
				$id = joni_place_attachment( $rel, $src );
			}
		}
		if ( $id ) {
			$map[ $base ] = $id;
		}
	}
	return $map;
}

function joni_step_media() {
	$map = joni_ensure_media();
	$wanted = joni_payload()['media'] ?? array();
	$log = array();
	foreach ( $wanted as $rel ) {
		$base = basename( $rel );
		$log[] = isset( $map[ $base ] )
			? "$base -> attachment {$map[$base]}"
			: "$base MISSING (not in payload/media and not on this site)";
	}
	return array( 'log' => $log );
}

function joni_step_content() {
	$payload = joni_payload();
	$items   = $payload['content'] ?? array();
	$media   = joni_ensure_media();
	$created = get_option( JONI_INSTALLER_CREATED, array() );
	$log     = array();

	foreach ( $items as $item ) {
		$type = $item['type'];
		$slug = $item['slug'];

		if ( ! post_type_exists( $type ) ) {
			return array( 'error' => "post type '$type' is not registered — run the joni-books step first" );
		}

		// upsert by slug, so re-running never duplicates
		$existing = get_posts( array(
			'post_type'      => $type,
			'name'           => $slug,
			'post_status'    => 'any',
			'posts_per_page' => 1,
		) );

		$data = array(
			'post_type'    => $type,
			'post_name'    => $slug,
			'post_title'   => $item['title'],
			'post_content' => $item['content'],
			'post_status'  => $item['status'] ?? 'publish',
		);
		if ( ! empty( $item['date'] ) ) {
			$data['post_date']     = $item['date'];
			$data['post_date_gmt'] = get_gmt_from_date( $item['date'] );
		}

		if ( $existing ) {
			$data['ID'] = $existing[0]->ID;
			$id         = wp_update_post( $data, true );
			$verb       = 'updated';
		} else {
			$id = wp_insert_post( $data, true );
			$verb = 'created';
			if ( ! is_wp_error( $id ) ) {
				$created[] = $id;
				update_option( JONI_INSTALLER_CREATED, $created, false );
			}
		}
		if ( is_wp_error( $id ) ) {
			return array( 'error' => "$slug: " . $id->get_error_message() );
		}

		foreach ( (array) ( $item['meta'] ?? array() ) as $k => $v ) {
			update_post_meta( $id, $k, $v );
		}

		// Taxonomy terms. wp_set_object_terms creates any term the taxonomy does
		// not have yet, which is how the book_category terms arrive — live has no
		// book_category before joni-books is active.
		foreach ( (array) ( $item['terms'] ?? array() ) as $taxonomy => $slugs ) {
			if ( ! taxonomy_exists( $taxonomy ) ) {
				$log[] = "$slug: taxonomy '$taxonomy' not registered, skipped";
				continue;
			}
			$res = wp_set_object_terms( $id, array_values( $slugs ), $taxonomy );
			if ( is_wp_error( $res ) ) {
				$log[] = "$slug: terms($taxonomy) FAILED: " . $res->get_error_message();
			} else {
				$log[] = "$slug: $taxonomy -> " . implode( ', ', $slugs );
			}
		}

		if ( ! empty( $item['thumb_file'] ) ) {
			$tid = $media[ basename( $item['thumb_file'] ) ] ?? 0;
			if ( $tid ) {
				set_post_thumbnail( $id, $tid );
			} else {
				$log[] = "$slug: WARNING featured image " . basename( $item['thumb_file'] ) . ' not found';
			}
		}

		$log[] = "$verb $type '$slug' (post $id)";
	}
	return array( 'log' => $log );
}

/** Category slug -> term IDs, created on demand. */
function joni_cat_ids( $slugs ) {
	$ids = array();
	foreach ( (array) $slugs as $slug ) {
		$t = get_term_by( 'slug', $slug, 'category' );
		if ( $t ) {
			$ids[] = (int) $t->term_id;
		}
	}
	return $ids;
}

/**
 * Create the categories the design needs and put existing posts back in them.
 *
 * The templates select News / Reviews / Events by category. On the live site all
 * 42 pre-existing posts were in "uncategorized" and neither News nor Reviews
 * existed at all, so the news page and the events archive rendered empty even
 * though the templates were loading and running correctly. Categories are not
 * part of a content export, so they have to be carried explicitly.
 */
function joni_step_categories() {
	$p   = joni_payload();
	$log = array();

	foreach ( (array) ( $p['categories'] ?? array() ) as $slug => $name ) {
		$term = get_term_by( 'slug', $slug, 'category' );
		if ( $term ) {
			$log[] = "category '$slug' already exists (id {$term->term_id})";
			continue;
		}
		$r = wp_insert_term( $name, 'category', array( 'slug' => $slug ) );
		if ( is_wp_error( $r ) ) {
			$log[] = "category '$slug' FAILED: " . $r->get_error_message();
		} else {
			$log[] = "created category '$slug' (id {$r['term_id']})";
		}
	}

	$map    = (array) ( $p['post_categories'] ?? array() );
	$done   = 0;
	$missed = array();
	foreach ( $map as $post_slug => $cat_slugs ) {
		$found = get_posts( array(
			'name'           => $post_slug,
			'post_type'      => 'post',
			'post_status'    => 'any',
			'posts_per_page' => 1,
			'fields'         => 'ids',
		) );
		if ( ! $found ) {
			$missed[] = $post_slug;
			continue;
		}
		$ids = joni_cat_ids( $cat_slugs );
		if ( ! $ids ) {
			continue;
		}
		wp_set_object_terms( $found[0], $ids, 'category' ); // replaces, so "uncategorized" drops away
		$done++;
	}
	$log[] = "put $done post(s) into their categories";
	if ( $missed ) {
		$log[] = count( $missed ) . ' post(s) from the mapping were not found on this site and were skipped';
	}

	return array( 'log' => $log );
}

function joni_step_menus() {
	$spec = joni_payload()['menus']['create'] ?? array();
	$locs = joni_payload()['menus']['locations'] ?? array();
	$log  = array();

	foreach ( $spec as $menu_name => $items ) {
		$menu = wp_get_nav_menu_object( $menu_name );
		if ( ! $menu ) {
			$id = wp_create_nav_menu( $menu_name );
			if ( is_wp_error( $id ) ) {
				return array( 'error' => "create menu '$menu_name': " . $id->get_error_message() );
			}
			$menu = wp_get_nav_menu_object( $id );
			$log[] = "created menu '$menu_name'";
		} else {
			$log[] = "menu '$menu_name' already exists";
		}

		// skip items already present, so re-running does not duplicate them
		$existing = wp_get_nav_menu_items( $menu->term_id ) ?: array();
		$have     = array();
		foreach ( $existing as $it ) {
			$have[] = ( $it->object ?: 'custom' ) . ':' . ( $it->object_id ?: $it->url );
		}

		foreach ( $items as $item ) {
			$type = $item['type'];
			$ob   = $item['object'];

			// resolve the staging reference against THIS site
			$object_id = 0;
			if ( $type === 'post_type' ) {
				$found = get_posts( array( 'post_type' => $ob, 'name' => $item['slug'], 'post_status' => 'publish', 'posts_per_page' => 1 ) );
				if ( $found ) {
					$object_id = $found[0]->ID;
				}
			} elseif ( $type === 'taxonomy' ) {
				$term = get_term_by( 'slug', $item['slug'], $ob );
				if ( $term ) {
					$object_id = (int) $term->term_id;
				}
			}

			if ( ! $object_id ) {
				$log[] = "menu item '{$item['slug']}' SKIPPED — not found on this site";
				continue;
			}
			// Key on the OBJECT, matching how wp_get_nav_menu_items reports existing
			// items ($it->object is 'page'/'category', $it->type is 'post_type'/'taxonomy').
			// Comparing type against object made every existing item look new and
			// duplicated the whole menu.
			$key = $ob . ':' . $object_id;
			if ( in_array( $key, $have, true ) ) {
				$log[] = "menu item '{$item['slug']}' already in the menu ($key)";
				continue;
			}

			$args = array(
				'menu-item-title'     => $item['title'],
				'menu-item-type'      => $type,
				'menu-item-object'    => $ob,
				'menu-item-object-id' => $object_id,
				'menu-item-position'  => (int) ( $item['order'] ?? 0 ),
				'menu-item-status'    => 'publish',
			);
			$res = wp_update_nav_menu_item( $menu->term_id, 0, $args );
			if ( is_wp_error( $res ) ) {
				$log[] = "menu item '{$item['slug']}' FAILED: " . $res->get_error_message();
			} else {
				$log[] = "added menu item '{$item['slug']}' -> $key";
			}
		}
	}

	// nav_menu_locations is a theme mod too, so the target theme must be
	// active or the locations land in the old theme's option.
	joni_ensure_theme( $log );

	$locations = get_theme_mod( 'nav_menu_locations', array() );
	foreach ( $locs as $location => $menu_name ) {
		$menu = wp_get_nav_menu_object( $menu_name );
		if ( $menu ) {
			$locations[ $location ] = (int) $menu->term_id;
			$log[]                  = "location '$location' -> '$menu_name'";
		}
	}
	set_theme_mod( 'nav_menu_locations', $locations );

	return array( 'log' => $log );
}

/** The snapshot option name for the CURRENTLY active theme. */
function joni_snapshot_key() {
	return JONI_INSTALLER_SNAPSHOT . '_' . get_stylesheet();
}

/**
 * Make sure the target theme is ACTIVE before anything writes a theme mod.
 *
 * Theme mods are stored per active stylesheet — set_theme_mod() writes
 * `theme_mods_<stylesheet>` for whatever theme is active at that moment. The
 * migration's step order applies the design BEFORE the step that switches the
 * theme, so on a site still running its old theme every one of these calls was
 * written into that old theme's option and silently discarded: the header
 * design, the logo and the header button all never arrived. Verified by
 * switching a working install to another theme and running the step — the design
 * landed in theme_mods_twentytwentyfour.
 */
function joni_ensure_theme( &$log ) {
	$target = joni_payload()['settings']['theme'] ?? '';
	if ( ! $target ) {
		return true;
	}
	if ( get_stylesheet() === $target ) {
		$log[] = "theme '$target' is already active";
		return true;
	}
	if ( ! wp_get_theme( $target )->exists() ) {
		$log[] = "theme '$target' is NOT INSTALLED";
		return false;
	}
	switch_theme( $target );
	$log[] = "switched to theme '$target' (theme settings only stick when their theme is active)";
	return get_stylesheet() === $target;
}

function joni_step_design() {
	$d       = joni_payload()['design'] ?? array();
	$payload = joni_payload();
	$log     = array();

	if ( empty( $d ) ) {
		return array( 'error' => 'no design payload found' );
	}

	// This must come first: everything below writes theme mods, and they only
	// land if the target theme is the active one.
	if ( ! joni_ensure_theme( $log ) ) {
		return array(
			'error' => 'the target theme is not active, so writing theme settings now would put them in the wrong theme — install and activate it first',
			'log'   => $log,
		);
	}

	// snapshot once per theme, so Revert always returns to the pre-migration state
	$snap_key = joni_snapshot_key();
	if ( ! get_option( $snap_key ) ) {
		$snap = array( 'theme_mods' => array(), 'options' => array(), 'pages' => array(), 'custom_css' => null );
		foreach ( (array) ( $d['theme_mods'] ?? array() ) as $k => $v ) {
			$snap['theme_mods'][ $k ] = get_theme_mod( $k, null );
		}
		foreach ( (array) ( $d['widgets'] ?? array() ) as $opt => $v ) {
			$snap['options'][ $opt ] = get_option( $opt, null );
		}
		foreach ( (array) ( $d['page_content'] ?? array() ) as $slug => $v ) {
			$p = get_page_by_path( $slug );
			if ( $p ) {
				$snap['pages'][ $slug ] = $p->post_content;
			}
		}
		$css = wp_get_custom_css_post();
		if ( $css ) {
			$snap['custom_css'] = $css->post_content;
		}
		update_option( $snap_key, $snap, false );
		$log[] = 'snapshot of current design recorded (Revert is available)';
	}

	foreach ( (array) ( $d['theme_mods'] ?? array() ) as $k => $v ) {
		set_theme_mod( $k, $v );
	}
	$log[] = count( (array) ( $d['theme_mods'] ?? array() ) ) . ' theme settings applied';

	foreach ( (array) ( $d['widgets'] ?? array() ) as $opt => $v ) {
		update_option( $opt, $v );
	}
	$log[] = count( (array) ( $d['widgets'] ?? array() ) ) . ' widget option rows applied';

	if ( isset( $d['custom_css'] ) ) {
		wp_update_custom_css_post( $d['custom_css'] );
		$log[] = 'custom CSS applied';
	}

	if ( ! empty( $d['global_styles']['content'] ) ) {
		$name     = $d['global_styles']['post_name'] ?? 'wp-global-styles-blocksy';
		$existing = get_posts( array( 'post_type' => 'wp_global_styles', 'name' => $name, 'post_status' => 'publish', 'numberposts' => 1 ) );
		if ( $existing ) {
			wp_update_post( array( 'ID' => $existing[0]->ID, 'post_content' => $d['global_styles']['content'] ) );
		} else {
			wp_insert_post( array(
				'post_type'    => 'wp_global_styles',
				'post_name'    => $name,
				'post_status'  => 'publish',
				'post_content' => $d['global_styles']['content'],
				'tax_input'    => array( 'wp_theme' => array( get_stylesheet() ) ),
			) );
		}
		$log[] = 'global styles applied';
	}

	if ( ! empty( $d['logo_file'] ) ) {
		$id = joni_find_attachment_by_basename( basename( $d['logo_file'] ) );
		if ( $id ) {
			set_theme_mod( 'custom_logo', $id );
			$log[] = "logo set to attachment $id";
		} else {
			$log[] = 'LOGO SKIPPED — ' . basename( $d['logo_file'] ) . ' is not in the media library';
		}
	}

	if ( ! empty( $d['menus'] ) ) {
		$log[] = 'menu locations are handled by the Build the navigation menu step';
	}

	foreach ( (array) ( $d['page_content'] ?? array() ) as $slug => $content ) {
		$p = get_page_by_path( $slug );
		if ( $p ) {
			wp_update_post( array( 'ID' => $p->ID, 'post_content' => $content ) );
			$log[] = "page '$slug' content replaced in place (post {$p->ID})";
		} else {
			$log[] = "page '$slug' not found";
		}
	}

	return array( 'log' => $log );
}

function joni_step_finish() {
	$p   = joni_payload();
	$log = array();
	$theme = $p['settings']['theme'] ?? 'blocksy';

	if ( get_stylesheet() !== $theme ) {
		switch_theme( $theme );
		$log[] = "theme switched to $theme";
	} else {
		$log[] = "$theme already active";
	}

	$slug = $p['settings']['front_page_slug'] ?? 'home';
	$home = get_page_by_path( $slug );
	if ( $home ) {
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $home->ID );
		$log[] = "static front page set to '$slug' (post {$home->ID})";
	} else {
		return array( 'error' => "front page '$slug' not found — run the content step first" );
	}

	flush_rewrite_rules( false );
	$log[] = 'rewrite rules flushed';
	return array( 'log' => $log );
}

function joni_run_step( $step ) {
	switch ( $step ) {
		case 'theme':
			return joni_step_theme();
		case 'plugins':
			return joni_step_plugins();
		case 'joni-books':
			return joni_step_joni_books();
		case 'media':
			return joni_step_media();
		case 'content':
			return joni_step_content();
		case 'categories':
			return joni_step_categories();
		case 'menus':
			return joni_step_menus();
		case 'design':
			return joni_step_design();
		case 'finish':
			return joni_step_finish();
	}
	return array( 'error' => "unknown step '$step'" );
}

/** Put back everything the design step and the content step changed. */
function joni_revert() {
	$snap = get_option( joni_snapshot_key() );
	if ( $snap ) {
		foreach ( (array) $snap['theme_mods'] as $k => $v ) {
			if ( $v === null ) {
				remove_theme_mod( $k );
			} else {
				set_theme_mod( $k, $v );
			}
		}
		foreach ( (array) $snap['options'] as $opt => $v ) {
			update_option( $opt, $v );
		}
		foreach ( (array) ( $snap['pages'] ?? array() ) as $slug => $content ) {
			$p = get_page_by_path( $slug );
			if ( $p ) {
				wp_update_post( array( 'ID' => $p->ID, 'post_content' => $content ) );
			}
		}
		if ( $snap['custom_css'] !== null ) {
			wp_update_custom_css_post( $snap['custom_css'] );
		}
		delete_option( joni_snapshot_key() );
	}

	$trashed = 0;
	foreach ( (array) get_option( JONI_INSTALLER_CREATED, array() ) as $id ) {
		if ( get_post( $id ) ) {
			wp_trash_post( $id );
			$trashed++;
		}
	}
	delete_option( JONI_INSTALLER_CREATED );

	return array( 'snapshot' => $snap ? 'restored' : 'none recorded', 'posts_trashed' => $trashed );
}

// ------------------------------------------------------------------ plumbing

add_action( 'admin_menu', function () {
	add_management_page( 'Joni Site Installer', 'Joni Site Installer', 'manage_options', 'joni-installer', 'joni_installer_page' );
} );

/**
 * Run a step and always answer with JSON.
 *
 * Without this wrapper a PHP fatal in a step returns WordPress's HTML error
 * page, and the browser can only report "SyntaxError: Unexpected token '<'",
 * which says nothing about what actually broke. Every failure mode — fatal,
 * uncaught exception, stray output — has to come back as a readable message.
 */
function joni_ajax( $work ) {
	check_ajax_referer( 'joni_installer' );
	if ( ! current_user_can( 'manage_options' ) ) {
		wp_send_json_error( array( 'error' => 'insufficient permissions' ) );
	}

	@set_time_limit( 300 );
	wp_raise_memory_limit( 'admin' );

	$sent = false;
	register_shutdown_function( function () use ( &$sent ) {
		if ( $sent ) {
			return;
		}
		// Discard whatever is buffered, the fatal's own output included, so the
		// response is JSON and not a half-rendered error page.
		while ( ob_get_level() > 0 ) {
			ob_end_clean();
		}
		$e = error_get_last();
		wp_send_json_error( array(
			'error' => $e
				? sprintf( 'PHP error: %s in %s:%d', $e['message'], $e['file'], $e['line'] )
				: 'the request ended without producing a result',
		) );
	} );

	ob_start();
	try {
		$result = call_user_func( $work );
	} catch ( Throwable $t ) {
		$result = array( 'error' => sprintf( 'exception: %s (%s:%d)', $t->getMessage(), $t->getFile(), $t->getLine() ) );
	}
	$noise = trim( ob_get_clean() );
	$sent  = true;

	if ( $noise !== '' ) {
		$result['stray_output'] = substr( $noise, 0, 1000 );
	}
	wp_send_json_success( $result );
}

add_action( 'wp_ajax_joni_installer_step', function () {
	joni_ajax( function () {
		return joni_run_step( sanitize_key( $_POST['step'] ?? '' ) );
	} );
} );

add_action( 'wp_ajax_joni_installer_revert', function () {
	joni_ajax( 'joni_revert' );
} );

function joni_installer_page() {
	$steps    = joni_step_list();
	$snapshot = get_option( joni_snapshot_key() );
	$payload  = joni_payload();
	?>
	<div class="wrap">
		<h1>Joni Site Installer</h1>
		<p>
			Brings the redesigned site across from staging: theme, plugins, content, images and the
			Blocksy design. Every step checks the current state first and is safe to re-run, so a run
			that stops halfway resumes where it left off.
		</p>

		<?php if ( empty( $payload ) ) : ?>
			<div class="notice notice-error"><p>
				<strong>payload/site.json is missing from this plugin.</strong> Re-download the package —
				you are running an incomplete copy.
			</p></div>
		<?php else : ?>
			<p>
				Payload built from <code><?php echo esc_html( $payload['from'] ?? 'staging' ); ?></code>:
				<?php echo count( (array) ( $payload['content'] ?? array() ) ); ?> content items,
				<?php echo count( (array) ( $payload['design']['theme_mods'] ?? array() ) ); ?> design settings.
			</p>
		<?php endif; ?>

		<table class="widefat striped" style="max-width:900px">
			<thead><tr><th style="width:40px">#</th><th>Step</th><th style="width:90px">Status</th></tr></thead>
			<tbody>
			<?php $i = 0; foreach ( $steps as $key => $label ) : $i++; ?>
				<tr>
					<td><?php echo $i; ?></td>
					<td><?php echo esc_html( $label ); ?></td>
					<td data-step-status="<?php echo esc_attr( $key ); ?>">—</td>
				</tr>
			<?php endforeach; ?>
			</tbody>
		</table>

		<p style="margin-top:1em">
			<button class="button button-primary" id="joni-run">Run all steps</button>
			<?php if ( $snapshot ) : ?>
				<button class="button" id="joni-revert">Revert the design and remove created posts</button>
			<?php endif; ?>
		</p>

		<pre id="joni-log" style="max-width:900px;max-height:420px;overflow:auto;background:#fff;border:1px solid #c3c4c7;padding:12px;white-space:pre-wrap"></pre>

		<p style="max-width:900px">
			<strong>When you are satisfied, deactivate and delete this plugin.</strong> It is a delivery
			mechanism, not something to leave running.
		</p>
	</div>

	<script>
	(function () {
		var steps = <?php echo wp_json_encode( array_keys( $steps ) ); ?>;
		var nonce = <?php echo wp_json_encode( wp_create_nonce( 'joni_installer' ) ); ?>;
		var ajax  = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>;
		var log   = document.getElementById('joni-log');
		var run   = document.getElementById('joni-run');

		function say(line) { log.textContent += line + "\n"; log.scrollTop = log.scrollHeight; }

		// Read the body as text first. A WordPress fatal returns an HTML error page,
		// and r.json() then throws a bare "Unexpected token '<'" that says nothing
		// about the cause — so surface whatever actually came back instead.
		function call(action, step) {
			var body = new URLSearchParams({ action: action, _ajax_nonce: nonce });
			if (step) { body.append('step', step); }
			return fetch(ajax, {
				method: 'POST',
				credentials: 'same-origin',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body: body.toString()
			}).then(function (r) {
				return r.text().then(function (t) {
					try {
						return JSON.parse(t);
					} catch (e) {
						return { success: false, data: {
							error: 'the server returned a web page instead of JSON (HTTP ' + r.status +
							       '), so the step hit a PHP error. The response began: ' +
							       t.replace(/\s+/g, ' ').trim().slice(0, 800)
						} };
					}
				});
			});
		}

		function mark(step, text, ok) {
			var el = document.querySelector('[data-step-status="' + step + '"]');
			if (el) { el.textContent = text; el.style.color = ok ? '#008a20' : '#d63638'; }
		}

		function runStep(i) {
			if (i >= steps.length) { say("\nDone. Check the site, then deactivate and delete this plugin."); run.disabled = false; return; }
			var step = steps[i];
			mark(step, 'running', true);
			say("\n== " + step + " ==");
			call('joni_installer_step', step).then(function (res) {
				var d = (res && res.data) ? res.data : { error: 'no response body' };
				if (d.stray_output) { say("   [output during the step] " + d.stray_output); }
				if (d.error) { mark(step, 'FAILED', false); say("ERROR: " + d.error); run.disabled = false; return; }
				(d.log || []).forEach(function (l) { say("   " + l); });
				mark(step, 'ok', true);
				runStep(i + 1);
			}).catch(function (e) {
				mark(step, 'FAILED', false); say("REQUEST FAILED: " + e); run.disabled = false;
			});
		}

		run.addEventListener('click', function () {
			run.disabled = true;
			log.textContent = '';
			runStep(0);
		});

		var rev = document.getElementById('joni-revert');
		if (rev) {
			rev.addEventListener('click', function () {
				if (!confirm('Undo the design and trash the posts this plugin created?')) { return; }
				call('joni_installer_revert').then(function (res) {
					say("revert: " + JSON.stringify(res && res.data ? res.data : res));
				});
			});
		}
	})();
	</script>
	<?php
}