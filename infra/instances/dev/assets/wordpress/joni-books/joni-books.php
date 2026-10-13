<?php
/**
 * Plugin Name: Joni Schwartz Books & Events
 * Description: Custom post type, taxonomy, book detail template, events templates, and homepage carousel/events list.
 * Version: 1.1.0
 * Author: Robbie
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// 1. Register Custom Post Type & Taxonomy
add_action( 'init', 'joni_register_books_cpt_and_tax' );
function joni_register_books_cpt_and_tax() {
    // Taxonomy: book_category
    $tax_labels = array(
        'name'              => _x( 'Book Categories', 'taxonomy general name' ),
        'singular_name'     => _x( 'Book Category', 'taxonomy singular name' ),
        'search_items'      => __( 'Search Book Categories' ),
        'all_items'         => __( 'All Book Categories' ),
        'parent_item'       => __( 'Parent Book Category' ),
        'parent_item_colon' => __( 'Parent Book Category:' ),
        'edit_item'         => __( 'Edit Book Category' ),
        'update_item'       => __( 'Update Book Category' ),
        'add_new_item'      => __( 'Add New Book Category' ),
        'new_item_name'     => __( 'New Book Category Name' ),
        'menu_name'         => __( 'Book Categories' ),
    );

    register_taxonomy( 'book_category', array( 'book' ), array(
        'hierarchical'      => true,
        'labels'            => $tax_labels,
        'show_ui'           => true,
        'show_admin_column' => true,
        'query_var'         => true,
        'rewrite'           => array( 'slug' => 'book-category' ),
        'show_in_rest'      => true,
    ) );

    // Post Type: book
    $cpt_labels = array(
        'name'               => _x( 'Books', 'post type general name' ),
        'singular_name'      => _x( 'Book', 'post type singular name' ),
        'menu_name'          => _x( 'Books', 'admin menu' ),
        'name_admin_bar'     => _x( 'Book', 'add new on admin bar' ),
        'add_new'            => _x( 'Add New', 'book' ),
        'add_new_item'       => __( 'Add New Book' ),
        'new_item'           => __( 'New Book' ),
        'edit_item'          => __( 'Edit Book' ),
        'view_item'          => __( 'View Book' ),
        'all_items'          => __( 'All Books' ),
        'search_items'       => __( 'Search Books' ),
        'parent_item_colon'  => __( 'Parent Books:' ),
        'not_found'          => __( 'No books found.' ),
        'not_found_in_trash' => __( 'No books found in Trash.' ),
    );

    $args = array(
        'labels'             => $cpt_labels,
        'description'        => __( 'Books authored or edited by Dr. Joni Schwartz-Chaney.' ),
        'public'             => true,
        'publicly_queryable' => true,
        'show_ui'            => true,
        'show_in_menu'       => true,
        'query_var'          => true,
        'rewrite'            => array( 'slug' => 'book', 'with_front' => false ),
        'capability_type'    => 'post',
        'has_archive'        => true,
        'hierarchical'       => false,
        'menu_position'      => 5,
        'menu_icon'          => 'dashicons-book-alt',
        'supports'           => array( 'title', 'editor', 'thumbnail', 'excerpt', 'custom-fields', 'page-attributes' ),
        'taxonomies'         => array( 'book_category' ),
        'show_in_rest'       => true,
    );

    register_post_type( 'book', $args );
}

// Flush rewrites once if not done
add_action( 'init', 'joni_check_flush_rewrites', 99 );
function joni_check_flush_rewrites() {
    if ( get_option( 'joni_books_rewrites_flushed_v2' ) !== 'yes' ) {
        flush_rewrite_rules( false );
        update_option( 'joni_books_rewrites_flushed_v2', 'yes' );
    }
}

// Purple header (matches the footer #102136) — global style
add_action( 'wp_head', 'joni_purple_header_css', 999 );

/**
 * Front-page hero image, driven by the page's Featured Image.
 *
 * The hero is a Stackable Columns block with a background image baked into its
 * attributes, so changing it currently means opening the block editor and
 * touching the block. Setting the Featured Image on the Home page is a single
 * click and survives edits to the hero block itself.
 *
 * Deliberately does nothing when no Featured Image is set, so the block's own
 * background remains the fallback and nothing breaks on a site that has not
 * opted in.
 */
add_action( 'wp_head', 'joni_featured_hero_css', 1000 );
function joni_featured_hero_css() {
    if ( ! is_front_page() ) {
        return;
    }
    $post_id = get_queried_object_id();
    if ( ! $post_id ) {
        return;
    }
    $thumb = get_post_thumbnail_id( $post_id );
    if ( ! $thumb ) {
        return;
    }
    $url = wp_get_attachment_image_url( $thumb, 'full' );
    if ( ! $url ) {
        return;
    }

    // Find the background block's id instead of hardcoding it: the block gets a
    // new uniqueId if it is ever re-created, and a hardcoded selector would then
    // fail silently — the hero would just stop responding to the featured image.
    $uid = joni_find_background_block_id( get_post_field( 'post_content', $post_id ) );
    if ( ! $uid ) {
        return;
    }

    printf(
        '<style id="joni-featured-hero">.stk-%s{background-image:url(%s)!important;}</style>',
        esc_attr( $uid ),
        esc_url( $url )
    );
}

/** The uniqueId of the first Stackable block in $content that has a background. */
function joni_find_background_block_id( $content ) {
    if ( ! preg_match_all( '/<!--\s+wp:stackable\/([\w-]+)\s+(\{.*?\})\s*-->/s', $content, $m, PREG_SET_ORDER ) ) {
        return '';
    }
    foreach ( $m as $block ) {
        $attrs = json_decode( $block[2], true );
        if ( is_array( $attrs ) && ! empty( $attrs['hasBackground'] ) && ! empty( $attrs['uniqueId'] ) ) {
            return $attrs['uniqueId'];
        }
    }
    return '';
}
function joni_purple_header_css() {
    ?>
    <style id="joni-purple-header">
        /* Purple header matching the footer */
        .ct-header [data-row*="middle"] {
            background-color: #102136 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
        }
        /* Keep the transparent header (homepage hero) transparent */
        .ct-header [data-transparent-row="yes"] {
            background-color: transparent !important;
            border-bottom: none !important;
        }
        /* White nav text */
        .ct-header .ct-menu-link {
            color: #ffffff !important;
        }
        .ct-header .ct-menu-link:hover {
            color: #90cdf4 !important;
        }
        /* White logo (invert the dark logo) */
        .ct-header .site-logo-container img[src*="logo-dark"] {
            filter: brightness(0) invert(1) !important;
        }
        /* CTA button */
        .ct-header .ct-header-cta .ct-button {
            background-color: #ffffff !important;
            color: #102136 !important;
        }
        .ct-header .ct-header-cta .ct-button:hover {
            background-color: #5e3fde !important;
            color: #ffffff !important;
        }
        /* Spacing for page containers below header */
        .joni-book-page,
        .joni-event-page,
        .joni-events-archive-page {
            position: relative !important;
            z-index: 1 !important;
            margin-top: 0 !important;
            padding-top: 40px !important;
        }
        /*
         * Singular hero section — match the header.
         *
         * A post with no featured image falls back to the hero's default
         * background, which is the light palette-6 (#F3F5F9), while the page
         * title is styled light palette-5 (#E7EBEE). Light text on a light
         * background leaves the heading almost unreadable. Posts WITH a featured
         * image are unaffected: the image sits in its own <figure> above this
         * colour, so it still shows.
         */
        .hero-section[data-type="type-1"],
        .hero-section[data-type="type-2"] {
            background-color: #102136 !important;
        }
    </style>
    <?php
}

// 4. Custom Meta Box for Book Details & Retailer Links
add_action( 'add_meta_boxes', 'joni_register_book_meta_boxes' );
function joni_register_book_meta_boxes() {
    add_meta_box(
        'joni_book_meta',
        __( 'Book Details & Retail Links', 'joni' ),
        'joni_book_meta_box_html',
        'book',
        'normal',
        'high'
    );
}

function joni_book_meta_box_html( $post ) {
    wp_nonce_field( 'joni_book_meta_nonce', 'joni_book_meta_nonce_field' );

    $author          = get_post_meta( $post->ID, '_book_author', true ) ?: 'Dr. Joni Schwartz-Chaney';
    $subtitle        = get_post_meta( $post->ID, '_book_subtitle', true );
    $publisher       = get_post_meta( $post->ID, '_book_publisher', true );
    $pub_year        = get_post_meta( $post->ID, '_book_pub_year', true );
    $isbn            = get_post_meta( $post->ID, '_book_isbn', true );
    $amazon_url      = get_post_meta( $post->ID, '_book_amazon_url', true );
    $publisher_url   = get_post_meta( $post->ID, '_book_publisher_url', true );
    $retailer_url    = get_post_meta( $post->ID, '_book_retailer_url', true );
    $retailer_label  = get_post_meta( $post->ID, '_book_retailer_label', true ) ?: 'Barnes & Noble';
    $pages           = get_post_meta( $post->ID, '_book_pages', true );
    ?>
    <style>
        .joni-meta-row { margin-bottom: 15px; }
        .joni-meta-row label { display: block; font-weight: 600; margin-bottom: 4px; }
        .joni-meta-row input[type="text"], .joni-meta-row input[type="url"] { width: 100%; max-width: 600px; }
        .joni-meta-group { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 15px; }
        .joni-meta-group > div { flex: 1; min-width: 200px; }
    </style>
    <div class="joni-meta-row">
        <label for="book_author"><?php _e( 'Author(s)', 'joni' ); ?></label>
        <input type="text" id="book_author" name="_book_author" value="<?php echo esc_attr( $author ); ?>" />
    </div>
    <div class="joni-meta-row">
        <label for="book_subtitle"><?php _e( 'Subtitle', 'joni' ); ?></label>
        <input type="text" id="book_subtitle" name="_book_subtitle" value="<?php echo esc_attr( $subtitle ); ?>" />
    </div>
    <div class="joni-meta-group">
        <div>
            <label for="book_publisher"><?php _e( 'Publisher', 'joni' ); ?></label>
            <input type="text" id="book_publisher" name="_book_publisher" value="<?php echo esc_attr( $publisher ); ?>" />
        </div>
        <div>
            <label for="book_pub_year"><?php _e( 'Publication Year', 'joni' ); ?></label>
            <input type="text" id="book_pub_year" name="_book_pub_year" value="<?php echo esc_attr( $pub_year ); ?>" />
        </div>
        <div>
            <label for="book_isbn"><?php _e( 'ISBN', 'joni' ); ?></label>
            <input type="text" id="book_isbn" name="_book_isbn" value="<?php echo esc_attr( $isbn ); ?>" />
        </div>
        <div>
            <label for="book_pages"><?php _e( 'Page Count', 'joni' ); ?></label>
            <input type="number" min="1" step="1" id="book_pages" name="_book_pages" value="<?php echo esc_attr( $pages ); ?>" placeholder="e.g. 212" />
            <p class="description" style="font-size:12px;color:#666;margin:4px 0 0;">Drives the 3D book thickness. Leave blank until known.</p>
        </div>
    </div>
    <hr style="margin: 20px 0; border: 0; border-top: 1px solid #ddd;" />
    <h4 style="margin-bottom: 12px;"><?php _e( 'Retailer Purchase Links (Elisabeth Elliot style buttons)', 'joni' ); ?></h4>
    <div class="joni-meta-row">
        <label for="book_amazon_url"><?php _e( 'Amazon URL', 'joni' ); ?></label>
        <input type="url" id="book_amazon_url" name="_book_amazon_url" value="<?php echo esc_attr( $amazon_url ); ?>" placeholder="https://www.amazon.com/..." />
    </div>
    <div class="joni-meta-row">
        <label for="book_publisher_url"><?php _e( 'Publisher Store URL', 'joni' ); ?></label>
        <input type="url" id="book_publisher_url" name="_book_publisher_url" value="<?php echo esc_attr( $publisher_url ); ?>" placeholder="https://fortresspress.com/... or https://rowman.com/..." />
    </div>
    <div class="joni-meta-group">
        <div>
            <label for="book_retailer_label"><?php _e( 'Third Retailer Button Label', 'joni' ); ?></label>
            <input type="text" id="book_retailer_label" name="_book_retailer_label" value="<?php echo esc_attr( $retailer_label ); ?>" />
        </div>
        <div style="flex: 2;">
            <label for="book_retailer_url"><?php _e( 'Third Retailer URL', 'joni' ); ?></label>
            <input type="url" id="book_retailer_url" name="_book_retailer_url" value="<?php echo esc_attr( $retailer_url ); ?>" />
        </div>
    </div>
    <?php
}

/* Page count: positive integer or empty string (never 0 / never garbage). */
function joni_sanitize_pages( $value ) {
    $value = trim( (string) $value );
    if ( $value === '' ) { return ''; }
    $n = absint( $value );
    return $n > 0 ? (string) $n : '';
}

add_action( 'save_post_book', 'joni_save_book_meta' );
function joni_save_book_meta( $post_id ) {
    if ( ! isset( $_POST['joni_book_meta_nonce_field'] ) || ! wp_verify_nonce( $_POST['joni_book_meta_nonce_field'], 'joni_book_meta_nonce' ) ) {
        return;
    }
    if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
        return;
    }
    if ( ! current_user_can( 'edit_post', $post_id ) ) {
        return;
    }

    $fields = array(
        '_book_author'         => 'sanitize_text_field',
        '_book_subtitle'       => 'sanitize_text_field',
        '_book_publisher'      => 'sanitize_text_field',
        '_book_pub_year'       => 'sanitize_text_field',
        '_book_isbn'           => 'sanitize_text_field',
        '_book_pages'          => 'joni_sanitize_pages',
        '_book_amazon_url'     => 'esc_url_raw',
        '_book_publisher_url'  => 'esc_url_raw',
        '_book_retailer_url'   => 'esc_url_raw',
        '_book_retailer_label' => 'sanitize_text_field',
    );

    foreach ( $fields as $field => $sanitizer ) {
        if ( isset( $_POST[ $field ] ) ) {
            update_post_meta( $post_id, $field, call_user_func( $sanitizer, $_POST[ $field ] ) );
        }
    }
}

// 5. Template Loader for Books and Events
/**
 * Resolve a category term ID from its SLUG.
 *
 * Templates must never hardcode term IDs. IDs are per-site: the staging IDs
 * (13 = News, 20 = Reviews, 21 = Events) do not exist on any other install, so a
 * hardcoded `'cat' => 21` silently queries an unrelated category and the loop
 * renders empty — the page looks broken while nothing reports an error.
 */
function joni_category_id( $slug ) {
    $term = get_category_by_slug( $slug );
    return $term ? (int) $term->term_id : 0;
}

/** Several category IDs at once, skipping any slug that does not exist. */
function joni_category_ids( $slugs ) {
    $ids = array();
    foreach ( (array) $slugs as $slug ) {
        $id = joni_category_id( $slug );
        if ( $id ) {
            $ids[] = $id;
        }
    }
    return $ids;
}

add_filter( 'template_include', 'joni_custom_template_loader', 99 );
function joni_custom_template_loader( $template ) {
    if ( is_singular( 'book' ) ) {
        $custom_template = plugin_dir_path( __FILE__ ) . 'templates/single-book.php';
        if ( file_exists( $custom_template ) ) {
            return $custom_template;
        }
    }

    // Match on slug only. The old `|| is_category( 21 )` fallback was a staging
    // term ID; on any other site 21 either does not exist or is a different
    // category entirely.
    if ( is_category( 'events' ) ) {
        $events_archive = plugin_dir_path( __FILE__ ) . 'templates/category-events.php';
        if ( file_exists( $events_archive ) ) {
            return $events_archive;
        }
    }

    if ( is_singular( 'post' ) && in_category( 'events' ) ) {
        $single_event = plugin_dir_path( __FILE__ ) . 'templates/single-event.php';
        if ( file_exists( $single_event ) ) {
            return $single_event;
        }
    }

    if ( is_page( 'news' ) ) {
        $news_page = plugin_dir_path( __FILE__ ) . 'templates/page-news.php';
        if ( file_exists( $news_page ) ) {
            return $news_page;
        }
    }

    return $template;
}

// 6. Homepage Carousel Shortcode: [joni_books_carousel]
add_shortcode( 'joni_books_carousel', 'joni_books_carousel_shortcode' );
function joni_books_carousel_shortcode( $atts ) {
    $atts = shortcode_atts( array(
        'limit'   => -1,
        'orderby' => 'menu_order date',
        'order'   => 'ASC',
    ), $atts, 'joni_books_carousel' );

    $query = new WP_Query( array(
        'post_type'      => 'book',
        'posts_per_page' => intval( $atts['limit'] ),
        'post_status'    => 'publish',
        'orderby'        => $atts['orderby'],
        'order'          => $atts['order'],
    ) );

    if ( ! $query->have_posts() ) {
        return '';
    }

    $carousel_id = 'joni-carousel-' . wp_rand( 1000, 9999 );

    ob_start();
    ?>
    <style>
    /* Carousel Styles */
    .joni-books-carousel-section {
        width: 100%;
        max-width: 1200px;
        margin: 0 auto;
        position: relative;
        padding: 10px 0 30px;
        user-select: none;
    }
    .joni-carousel-wrapper {
        position: relative;
        overflow: hidden;
        padding: 20px 4px 28px;
    }
    .joni-carousel-track {
        display: flex;
        gap: 28px;
        overflow-x: auto;
        scroll-behavior: smooth;
        scroll-snap-type: x mandatory;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        padding: 10px 4px 20px;
    }
    .joni-carousel-track::-webkit-scrollbar {
        display: none;
    }
    .joni-carousel-card {
        flex: 0 0 calc(25% - 21px);
        min-width: 220px;
        max-width: 280px;
        scroll-snap-align: center;
        background: #ffffff;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
        transition: transform 0.28s ease, box-shadow 0.28s ease;
        display: flex;
        flex-direction: column;
        text-decoration: none !important;
        color: inherit !important;
        border: 1px solid #edf2f7;
    }
    .joni-carousel-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 16px 32px rgba(0,0,0,0.12), 0 3px 8px rgba(0,0,0,0.06);
    }
    @media (max-width: 1024px) {
        .joni-carousel-card {
            flex: 0 0 calc(33.333% - 19px);
        }
    }
    @media (max-width: 768px) {
        .joni-carousel-card {
            flex: 0 0 calc(50% - 14px);
            min-width: 190px;
        }
    }
    @media (max-width: 480px) {
        .joni-carousel-card {
            flex: 0 0 82%;
            min-width: 230px;
        }
    }
    .joni-card-cover-wrapper {
        width: 100%;
        aspect-ratio: 1 / 1.48;
        border-radius: 8px;
        overflow: hidden;
        background-color: #e2e8f0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-bottom: 14px;
        position: relative;
    }
    .joni-card-cover-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition: transform 0.3s ease;
    }
    .joni-carousel-card:hover .joni-card-cover-img {
        transform: scale(1.03);
    }
    .joni-card-badge {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #3182ce;
        background: #ebf8ff;
        padding: 3px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 8px;
        align-self: flex-start;
    }
    .joni-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1a202c;
        margin: 0 0 6px;
        line-height: 1.35;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .joni-card-author {
        font-size: 0.85rem;
        color: #718096;
        margin: 0 0 14px;
        flex-grow: 1;
    }
    .joni-card-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
        padding: 9px 12px;
        background: #1a202c;
        color: #ffffff !important;
        font-size: 0.88rem;
        font-weight: 600;
        border-radius: 6px;
        transition: background 0.2s;
        text-align: center;
        margin-top: auto;
    }
    .joni-carousel-card:hover .joni-card-btn {
        background: #3182ce;
    }
    /* Controls */
    .joni-carousel-arrow {
        position: absolute;
        top: 45%;
        transform: translateY(-50%);
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #2d3748;
        transition: all 0.2s ease;
        z-index: 10;
    }
    .joni-carousel-arrow:hover {
        background: #1a202c;
        color: #ffffff;
        border-color: #1a202c;
        transform: translateY(-50%) scale(1.08);
    }
    .joni-carousel-arrow.prev { left: -14px; }
    .joni-carousel-arrow.next { right: -14px; }
    @media (max-width: 768px) {
        .joni-carousel-arrow { display: none; }
    }
    /* Dots */
    .joni-carousel-dots {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-top: 12px;
    }
    .joni-carousel-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #cbd5e0;
        border: none;
        padding: 0;
        cursor: pointer;
        transition: all 0.25s ease;
    }
    .joni-carousel-dot.active {
        background: #3182ce;
        width: 24px;
        border-radius: 12px;
    }
    </style>

    <div class="joni-books-carousel-section" id="<?php echo esc_attr( $carousel_id ); ?>">
        <button class="joni-carousel-arrow prev" aria-label="Previous Books">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </button>
        <button class="joni-carousel-arrow next" aria-label="Next Books">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>

        <div class="joni-carousel-wrapper">
            <div class="joni-carousel-track">
                <?php
                while ( $query->have_posts() ) : $query->the_post();
                    $b_id = get_the_ID();
                    $b_author = get_post_meta( $b_id, '_book_author', true ) ?: 'Dr. Joni Schwartz-Chaney';
                    $b_pages  = get_post_meta( $b_id, '_book_pages', true );
                    $b_terms = get_the_terms( $b_id, 'book_category' );
                    $badge = ( ! empty( $b_terms ) && ! is_wp_error( $b_terms ) ) ? $b_terms[0]->name : 'Book';
                    $cover_url = has_post_thumbnail( $b_id ) ? get_the_post_thumbnail_url( $b_id, 'medium_large' ) : '';
                ?>
                    <a href="<?php the_permalink(); ?>" class="joni-carousel-card">
                        <div class="joni-card-cover-wrapper joni-3d-scene">
                            <?php if ( $cover_url ) : ?>
                                <div class="joni-book-3d">
                                    <div class="joni-book-3d-cover">
                                        <img src="<?php echo esc_url( $cover_url ); ?>" alt="<?php the_title_attribute(); ?>" class="joni-card-cover-img joni-book-3d-img" loading="lazy" />
                                    </div>
                                    <div class="joni-book-3d-spine"></div>
                                    <div class="joni-book-3d-pages" style="<?php echo esc_attr( joni_book_pages_style( $b_pages ) ); ?>"></div>
                                </div>
                            <?php else : ?>
                                <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#718096;font-size:0.9rem;padding:10px;text-align:center;">
                                    <?php the_title(); ?>
                                </div>
                            <?php endif; ?>
                        </div>
                        <span class="joni-card-badge"><?php echo esc_html( $badge ); ?></span>
                        <h3 class="joni-card-title"><?php the_title(); ?></h3>
                        <p class="joni-card-author"><?php echo esc_html( $b_author ); ?></p>
                        <span class="joni-card-btn">
                            <span>View Details</span>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                        </span>
                    </a>
                <?php endwhile; wp_reset_postdata(); ?>
            </div>
        </div>

        <div class="joni-carousel-dots"></div>
    </div>

    <script>
    (function() {
        const root = document.getElementById('<?php echo esc_js( $carousel_id ); ?>');
        if (!root) return;
        const track = root.querySelector('.joni-carousel-track');
        const prevBtn = root.querySelector('.joni-carousel-arrow.prev');
        const nextBtn = root.querySelector('.joni-carousel-arrow.next');
        const dotsContainer = root.querySelector('.joni-carousel-dots');
        const cards = track.querySelectorAll('.joni-carousel-card');

        if (!cards.length) return;

        cards.forEach((card, i) => {
            const dot = document.createElement('button');
            dot.className = 'joni-carousel-dot' + (i === 0 ? ' active' : '');
            dot.setAttribute('aria-label', 'Go to book ' + (i + 1));
            dot.addEventListener('click', () => {
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            });
            dotsContainer.appendChild(dot);
        });

        const dots = dotsContainer.querySelectorAll('.joni-carousel-dot');

        let scrollTimeout;
        track.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                const trackCenter = track.getBoundingClientRect().left + track.offsetWidth / 2;
                let closestIndex = 0;
                let closestDist = Infinity;
                cards.forEach((card, idx) => {
                    const box = card.getBoundingClientRect();
                    const cardCenter = box.left + box.width / 2;
                    const dist = Math.abs(trackCenter - cardCenter);
                    if (dist < closestDist) {
                        closestDist = dist;
                        closestIndex = idx;
                    }
                });
                dots.forEach((d, idx) => {
                    d.classList.toggle('active', idx === closestIndex);
                });
            }, 60);
        });

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                const scrollAmount = track.offsetWidth * 0.75;
                track.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                const scrollAmount = track.offsetWidth * 0.75;
                track.scrollBy({ left: scrollAmount, behavior: 'smooth' });
            });
        }
    })();
    </script>
    <?php
    return ob_get_clean();
}

// 7. Books Grid Shortcode for the /books/ Catalog: [joni_books_grid]
add_shortcode( 'joni_books_grid', 'joni_books_grid_shortcode' );
function joni_books_grid_shortcode( $atts ) {
    $query = new WP_Query( array(
        'post_type'      => 'book',
        'posts_per_page' => -1,
        'post_status'    => 'publish',
        'orderby'        => 'menu_order date',
        'order'          => 'ASC',
    ) );

    if ( ! $query->have_posts() ) {
        return '<p>No books found.</p>';
    }

    ob_start();
    ?>
    <style>
    .joni-books-grid-wrap {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 36px;
        margin: 40px auto;
        max-width: 1140px;
    }
    .joni-grid-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.06);
        border: 1px solid #edf2f7;
        display: flex;
        flex-direction: column;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
        text-decoration: none !important;
        color: inherit !important;
    }
    .joni-grid-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 16px 36px rgba(0,0,0,0.12);
    }
    .joni-grid-cover-wrap {
        width: 100%;
        aspect-ratio: 1 / 1.48;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 16px;
        box-shadow: 0 6px 14px rgba(0,0,0,0.1);
        background: #e2e8f0;
    }
    .joni-grid-cover-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    <?php echo joni_3d_book_css(); ?>
    .joni-grid-badge {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #3182ce;
        background: #ebf8ff;
        padding: 3px 10px;
        border-radius: 999px;
        display: inline-block;
        margin-bottom: 10px;
        align-self: flex-start;
    }
    .joni-grid-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1a202c;
        margin: 0 0 8px;
        line-height: 1.3;
    }
    .joni-grid-author {
        font-size: 0.9rem;
        color: #718096;
        margin: 0 0 16px;
        flex-grow: 1;
    }
    .joni-grid-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 10px 16px;
        background: #1a202c;
        color: #ffffff !important;
        font-size: 0.92rem;
        font-weight: 600;
        border-radius: 6px;
        transition: background 0.2s;
        margin-top: auto;
    }
    .joni-grid-card:hover .joni-grid-btn {
        background: #3182ce;
    }
    </style>
    <div class="joni-books-grid-wrap">
        <?php while ( $query->have_posts() ) : $query->the_post();
            $b_id = get_the_ID();
            $b_author = get_post_meta( $b_id, '_book_author', true ) ?: 'Dr. Joni Schwartz-Chaney';
            $b_pages  = get_post_meta( $b_id, '_book_pages', true );
            $b_terms = get_the_terms( $b_id, 'book_category' );
            $badge = ( ! empty( $b_terms ) && ! is_wp_error( $b_terms ) ) ? $b_terms[0]->name : 'Book';
            $cover_url = has_post_thumbnail( $b_id ) ? get_the_post_thumbnail_url( $b_id, 'medium_large' ) : '';
        ?>
            <a href="<?php the_permalink(); ?>" class="joni-grid-card">
                <div class="joni-grid-cover-wrap joni-3d-scene">
                    <?php if ( $cover_url ) : ?>
                        <div class="joni-book-3d">
                            <div class="joni-book-3d-cover">
                                <img src="<?php echo esc_url( $cover_url ); ?>" alt="<?php the_title_attribute(); ?>" class="joni-grid-cover-img joni-book-3d-img" loading="lazy" />
                            </div>
                            <div class="joni-book-3d-spine"></div>
                            <div class="joni-book-3d-pages" style="<?php echo esc_attr( joni_book_pages_style( $b_pages ) ); ?>"></div>
                        </div>
                    <?php endif; ?>
                </div>
                <span class="joni-grid-badge"><?php echo esc_html( $badge ); ?></span>
                <h3 class="joni-grid-title"><?php the_title(); ?></h3>
                <p class="joni-grid-author"><?php echo esc_html( $b_author ); ?></p>
                <span class="joni-grid-btn">
                    <span>View Book Details</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </span>
            </a>
        <?php endwhile; wp_reset_postdata(); ?>
    </div>
    <?php
    return ob_get_clean();
}

// 8. Events Cards Shortcode: [joni_events_list]
add_shortcode( 'joni_events_list', 'joni_events_list_shortcode' );
function joni_events_list_shortcode( $atts ) {
    $atts = shortcode_atts( array(
        'count' => 2,
    ), $atts, 'joni_events_list' );

    // Resolve events by slug. 21 is staging's term ID — on any other install it
    // is a different category, so this shortcode rendered nothing on the homepage.
    $events_id = joni_category_id( 'events' );
    $args = array(
        'posts_per_page' => intval( $atts['count'] ),
        'post_status'    => 'publish',
        'orderby'        => 'date',
        'order'          => 'DESC',
    );
    if ( $events_id ) {
        $args['cat'] = $events_id;
    } else {
        $args['post__in'] = array( 0 );
    }
    $query = new WP_Query( $args );

    if ( ! $query->have_posts() ) {
        return '';
    }

    ob_start();
    ?>
    <style>
    @keyframes joniPulse {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .joni-events-grid-wrap {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
        gap: 32px;
        max-width: 1140px;
        margin: 28px auto 20px;
    }
    .joni-event-cool-card {
        background: #ffffff;
        border-radius: 16px;
        border: 1px solid #edf2f7;
        padding: 30px;
        box-shadow: 0 10px 30px -5px rgba(16, 33, 54, 0.07), 0 1px 3px rgba(16, 33, 54, 0.04);
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease;
        text-decoration: none !important;
        color: inherit !important;
    }
    .joni-event-cool-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3182ce, #805ad5, #dd6b20);
        opacity: 0.85;
        transition: height 0.25s ease;
    }
    .joni-event-cool-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 24px 45px -10px rgba(16, 33, 54, 0.16), 0 4px 10px rgba(16, 33, 54, 0.06);
        border-color: #cbd5e0;
    }
    .joni-event-cool-card:hover::before {
        height: 6px;
    }
    .joni-event-card-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    .joni-event-live-pill {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 4px 12px;
        background: #ecfdf5;
        color: #047857;
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-radius: 999px;
        border: 1px solid #a7f3d0;
    }
    .joni-live-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #10b981;
        animation: joniPulse 2s infinite;
    }
    .joni-event-time-pill {
        font-size: 0.82rem;
        font-weight: 600;
        color: #4a5568;
        background: #f7fafc;
        padding: 4px 12px;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
    }
    .joni-event-card-body {
        display: flex;
        gap: 24px;
        align-items: flex-start;
        margin-bottom: 24px;
        flex-grow: 1;
    }
    .joni-event-date-block {
        background: linear-gradient(145deg, #102136 0%, #1a365d 100%);
        border-radius: 12px;
        padding: 14px 12px;
        text-align: center;
        min-width: 78px;
        flex-shrink: 0;
        box-shadow: 0 6px 18px rgba(16, 33, 54, 0.22);
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .joni-event-month {
        color: #63b3ed;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        display: block;
        margin-bottom: 2px;
        line-height: 1;
    }
    .joni-event-day {
        color: #ffffff;
        font-size: 2.1rem;
        font-weight: 900;
        line-height: 1.05;
        display: block;
        margin-bottom: 4px;
    }
    .joni-event-weekday {
        color: #a0aec0;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        display: block;
        letter-spacing: 0.5px;
    }
    .joni-event-text-block {
        flex-grow: 1;
    }
    .joni-event-venue-title {
        font-size: 1.4rem;
        font-weight: 800;
        color: #102136;
        margin: 0 0 10px;
        line-height: 1.25;
        letter-spacing: -0.01em;
    }
    .joni-event-meta-location {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        font-size: 0.92rem;
        color: #4a5568;
        font-weight: 500;
        margin-bottom: 12px;
        line-height: 1.4;
    }
    .joni-event-meta-location svg {
        color: #3182ce;
        flex-shrink: 0;
        margin-top: 2px;
    }
    .joni-event-desc {
        font-size: 0.96rem;
        color: #718096;
        line-height: 1.6;
        margin: 0;
    }
    .joni-event-card-footer {
        display: flex;
        gap: 12px;
        align-items: center;
        padding-top: 20px;
        border-top: 1px solid #edf2f7;
        margin-top: auto;
    }
    .joni-event-btn-details {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        flex: 1;
        padding: 12px 20px;
        background: #102136;
        color: #ffffff !important;
        font-size: 0.92rem;
        font-weight: 600;
        border-radius: 8px;
        text-decoration: none;
        transition: all 0.25s ease;
        box-shadow: 0 2px 8px rgba(16, 33, 54, 0.15);
    }
    .joni-event-btn-details:hover {
        background: #3182ce;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(49, 130, 206, 0.35);
    }
    .joni-event-btn-details svg {
        transition: transform 0.2s ease;
    }
    .joni-event-btn-details:hover svg {
        transform: translateX(4px);
    }
    .joni-event-btn-map {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 12px 18px;
        background: #ffffff;
        color: #2d3748 !important;
        border: 1px solid #cbd5e0;
        font-size: 0.9rem;
        font-weight: 600;
        border-radius: 8px;
        text-decoration: none;
        transition: all 0.2s ease;
    }
    .joni-event-btn-map:hover {
        background: #f7fafc;
        border-color: #a0aec0;
        color: #1a202c !important;
        transform: translateY(-2px);
    }
    @media (max-width: 640px) {
        .joni-events-grid-wrap {
            grid-template-columns: 1fr;
        }
        .joni-event-card-body {
            flex-direction: column;
            gap: 16px;
        }
        .joni-event-date-block {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 16px;
            width: 100%;
            justify-content: flex-start;
        }
        .joni-event-day {
            font-size: 1.8rem;
            margin-bottom: 0;
        }
        .joni-event-card-footer {
            flex-direction: column;
        }
        .joni-event-btn-details,
        .joni-event-btn-map {
            width: 100%;
        }
    }
    </style>

    <div class="joni-events-grid-wrap">
        <?php
        while ( $query->have_posts() ) : $query->the_post();
            $ev_id = get_the_ID();
            $ev_date_formatted = get_post_meta( $ev_id, '_event_date_formatted', true );
            $ev_time           = get_post_meta( $ev_id, '_event_time', true );
            $ev_venue          = get_post_meta( $ev_id, '_event_venue', true );
            $ev_address        = get_post_meta( $ev_id, '_event_address', true );
            $ev_month          = get_post_meta( $ev_id, '_event_month', true );
            $ev_day            = get_post_meta( $ev_id, '_event_day', true );

            if ( empty( $ev_month ) || empty( $ev_day ) ) {
                $ev_month = get_the_date( 'M' );
                $ev_day   = get_the_date( 'd' );
            }

            $ev_date = get_post_meta( $ev_id, '_event_date', true );
            $ev_weekday = ! empty( $ev_date ) ? date_i18n( 'D', strtotime( $ev_date ) ) : 'Upcoming';

            if ( empty( $ev_venue ) ) {
                $title = get_the_title();
                if ( strpos( $title, '—' ) !== false ) {
                    $parts = explode( '—', $title );
                    $ev_venue = trim( $parts[0] );
                } else {
                    $ev_venue = $title;
                }
            }

            $maps_url = ! empty( $ev_address )
                ? 'https://www.google.com/maps/search/?api=1&query=' . urlencode( $ev_venue . ' ' . $ev_address )
                : '';
        ?>
            <div class="joni-event-cool-card">
                <div class="joni-event-card-topbar">
                    <span class="joni-event-live-pill">
                        <span class="joni-live-dot"></span> Author Reading &amp; Signing
                    </span>
                    <?php if ( ! empty( $ev_time ) ) : ?>
                        <span class="joni-event-time-pill"><?php echo esc_html( $ev_time ); ?></span>
                    <?php endif; ?>
                </div>

                <div class="joni-event-card-body">
                    <div class="joni-event-date-block">
                        <span class="joni-event-month"><?php echo esc_html( $ev_month ); ?></span>
                        <span class="joni-event-day"><?php echo esc_html( $ev_day ); ?></span>
                        <span class="joni-event-weekday"><?php echo esc_html( $ev_weekday ); ?></span>
                    </div>

                    <div class="joni-event-text-block">
                        <h3 class="joni-event-venue-title"><?php echo esc_html( $ev_venue ); ?></h3>
                        
                        <?php if ( ! empty( $ev_address ) ) : ?>
                            <div class="joni-event-meta-location">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                                <span><?php echo esc_html( $ev_address ); ?></span>
                            </div>
                        <?php endif; ?>

                        <p class="joni-event-desc">
                            Join Joni for an evening at <?php echo esc_html( $ev_venue ); ?> in Brooklyn discussing her latest writing, research, and publications.
                        </p>
                    </div>
                </div>

                <div class="joni-event-card-footer">
                    <a href="<?php the_permalink(); ?>" class="joni-event-btn-details">
                        <span>Event Details</span>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                    </a>
                    <?php if ( ! empty( $maps_url ) ) : ?>
                        <a href="<?php echo esc_url( $maps_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-event-btn-map" title="View location on Google Maps">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>
                            <span>Directions</span>
                        </a>
                    <?php endif; ?>
                </div>
            </div>
        <?php endwhile; wp_reset_postdata(); ?>
    </div>
    <?php
    return ob_get_clean();
}

/* ===== Latest News & Blog Posts ===== */
add_shortcode( 'joni_news_list', 'joni_news_list_shortcode' );
function joni_news_list_shortcode( $atts ) {
	$atts = shortcode_atts( array(
		'count' => 6,
	), $atts, 'joni_news_list' );

	// Resolve News + Reviews by slug — 13/20 are staging's term IDs and mean
	// nothing elsewhere, which is why the homepage news list was empty on live.
	$news_ids = joni_category_ids( array( 'news', 'reviews' ) );
	$args = array(
		'posts_per_page' => intval( $atts['count'] ),
		'post_status'    => 'publish',
		'orderby'        => 'date',
		'order'          => 'DESC',
	);
	if ( $news_ids ) {
		$args['category__in'] = $news_ids;
	} else {
		$args['post__in'] = array( 0 );
	}
	$query = new WP_Query( $args );

	if ( ! $query->have_posts() ) {
		return '';
	}

	ob_start();
	?>
	<style>
	.joni-news-grid-wrap {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 28px;
		max-width: 1140px;
		margin: 28px auto 20px;
	}
	.joni-news-card {
		background: #ffffff;
		border-radius: 16px;
		border: 1px solid #edf2f7;
		padding: 28px;
		box-shadow: 0 10px 30px -5px rgba(16, 33, 54, 0.07), 0 1px 3px rgba(16, 33, 54, 0.04);
		display: flex;
		flex-direction: column;
		position: relative;
		overflow: hidden;
		transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease;
	}
	.joni-news-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 4px;
		background: linear-gradient(90deg, #3182ce, #805ad5, #dd6b20);
		opacity: 0.85;
		transition: height 0.25s ease;
	}
	.joni-news-card:hover {
		transform: translateY(-8px);
		box-shadow: 0 24px 45px -10px rgba(16, 33, 54, 0.16), 0 4px 10px rgba(16, 33, 54, 0.06);
		border-color: #cbd5e0;
	}
	.joni-news-card:hover::before {
		height: 6px;
	}
	.joni-news-cat {
		display: inline-flex;
		align-self: flex-start;
		padding: 4px 12px;
		background: #ebf8ff;
		color: #2b6cb0;
		font-size: 0.74rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		border-radius: 999px;
		border: 1px solid #bee3f8;
		margin-bottom: 14px;
	}
	.joni-news-cat.joni-cat-reviews {
		background: #faf5ff;
		color: #6b46c1;
		border-color: #e9d8fd;
	}
	.joni-news-title {
		font-size: 1.22rem;
		font-weight: 800;
		color: #102136;
		margin: 0 0 10px;
		line-height: 1.3;
		letter-spacing: -0.01em;
	}
	.joni-news-title a {
		color: inherit;
		text-decoration: none;
	}
	.joni-news-title a:hover {
		color: #3182ce;
	}
	.joni-news-excerpt {
		font-size: 0.95rem;
		color: #718096;
		line-height: 1.6;
		margin: 0 0 18px;
		flex-grow: 1;
	}
	.joni-news-date {
		font-size: 0.82rem;
		font-weight: 600;
		color: #a0aec0;
		border-top: 1px solid #edf2f7;
		padding-top: 14px;
		margin-top: auto;
	}
	@media (max-width: 640px) {
		.joni-news-grid-wrap { grid-template-columns: 1fr; }
	}
	</style>

	<div class="joni-news-grid-wrap">
		<?php
		while ( $query->have_posts() ) : $query->the_post();
			$news_cat_name = 'News';
			$news_cat_slug = 'news';
			$cats = get_the_category();
			if ( ! empty( $cats ) ) {
				foreach ( $cats as $c ) {
					if ( in_array( $c->slug, array( 'news', 'reviews' ), true ) ) {
						$news_cat_name = $c->name;
						$news_cat_slug = $c->slug;
						break;
					}
				}
			}
			$news_excerpt = trim( wp_strip_all_tags( get_the_excerpt() ) );
			if ( empty( $news_excerpt ) || preg_match( '/^https?:\/\/\S+$/', $news_excerpt ) ) {
				$news_excerpt = trim( wp_strip_all_tags( get_the_content() ) );
			}
			if ( preg_match( '/^https?:\/\/\S+$/', $news_excerpt ) ) {
				$news_excerpt = '';
			}
			$news_excerpt = wp_trim_words( $news_excerpt, 24, '…' );
		?>
			<article class="joni-news-card">
				<span class="joni-news-cat joni-cat-<?php echo esc_attr( $news_cat_slug ); ?>"><?php echo esc_html( $news_cat_name ); ?></span>
				<h3 class="joni-news-title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h3>
				<?php if ( ! empty( $news_excerpt ) ) : ?>
					<p class="joni-news-excerpt"><?php echo esc_html( $news_excerpt ); ?></p>
				<?php endif; ?>
				<time class="joni-news-date"><?php echo get_the_date(); ?></time>
			</article>
		<?php endwhile; wp_reset_postdata(); ?>
	</div>
	<?php
	return ob_get_clean();
}

/* ===== 3D Book Cover Component (v3) =====
 * Book-shaped 3D covers: the cover image fills the whole face; spine and page edges
 * are built from the cover's own edge tone; drop shadow sits behind the book.
 * Card chrome (white box, border, card shadow) is removed so the book floats.
 */
function joni_3d_book_css() {
    static $done = false;
    if ( $done ) { return ''; }
    $done = true;
    return <<<CSS
/* ===== Card chrome removal: let the book float, no white box / border ===== */
.joni-books-grid-wrap .joni-grid-card,
.joni-books-carousel-section .joni-carousel-card {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    border-radius: 0 !important;
}
/* Hover lift now comes from the book itself, not the card box */
.joni-books-grid-wrap .joni-grid-card:hover,
.joni-books-carousel-section .joni-carousel-card:hover {
    transform: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
/* Re-add breathing room to the card text beneath the book */
.joni-books-grid-wrap .joni-grid-badge,
.joni-books-carousel-section .joni-card-badge { margin-top: 22px !important; }
.joni-grid-btn, .joni-card-btn {
    background: #1a202c !important;
    margin-top: 12px !important;
}

/* ===== The 3D scene ===== */
.joni-3d-scene {
    perspective: 1600px;
    perspective-origin: 50% 45%;
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    overflow: visible !important;
    border-radius: 0 !important;
    display: block !important;
    aspect-ratio: auto !important;
    min-height: 0 !important;
    margin-bottom: 0 !important;
    padding: 18px 14px 26px !important;
}

/* The book itself defines the shape -- cover aspect lives HERE. */
.joni-book-3d {
    position: relative;
    width: 100%;
    aspect-ratio: 1 / 1.48;
    transform-style: preserve-3d;
    transform: rotateY(-18deg);
    transition: transform 0.5s cubic-bezier(0.22, 0.61, 0.36, 1);
    will-change: transform;
    filter: drop-shadow(18px 16px 22px rgba(0, 0, 0, 0.28));
}
.joni-books-grid-wrap .joni-book-3d { transform: rotateY(-20deg); }

/* ===== Cover face: fills the entire book shape ===== */
.joni-book-3d .joni-book-3d-cover {
    position: absolute;
    inset: 0;
    overflow: hidden;
    background: #d7dbe2;
    border-radius: 1px 4px 4px 1px;
    transform: translateZ(6px);
    /* front cover sits above the page block */
    z-index: 2;
    box-shadow: inset 26px 0 30px -26px rgba(0, 0, 0, 0.55);
}
.joni-book-3d .joni-book-3d-img {
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
    object-position: center;
    display: block;
    border-radius: 1px 4px 4px 1px;
}

/* ===== Spine: narrow, wraps the left edge smoothly ===== */
.joni-book-3d .joni-book-3d-spine {
    position: absolute;
    top: 0;
    left: 0;
    width: 26px;
    height: 100%;
    transform: rotateY(-90deg) translateZ(6px);
    transform-origin: left center;
    background: linear-gradient(
        to right,
        #1c1f26 0%,
        #2a2f3a 45%,
        #3d434f 78%,
        #4a5160 100%
    );
    border-radius: 3px 0 0 3px;
}

/* ===== Page edges: a visible stack of leaves, width driven by page count ===== */
.joni-book-3d .joni-book-3d-pages {
    position: absolute;
    top: 3px;
    right: 0;
    width: var(--joni-pages-w, 16px);
    height: calc(100% - 6px);
    /* Rotate about the LEFT edge so the panel swings OUT to the right, then push it
     * forward to the cover plane (cover is at translateZ(6px)). Rotating about the
     * right edge instead would swing it backward, behind the cover -> invisible. */
    transform-origin: left center;
    transform: translateX(100%) rotateY(90deg) translateZ(6px);
    border-radius: 0 2px 2px 0;
    background-image: repeating-linear-gradient(
        to right,
        #ffffff 0px,
        #f2f4f7 var(--joni-leaf, 0.8px),
        #dadfe6 var(--joni-leaf, 0.8px),
        #eef1f5 calc(var(--joni-leaf, 0.8px) * 2)
    );
    background-color: #eef1f5;
    box-shadow:
        inset -3px 0 5px -2px rgba(0, 0, 0, 0.28),
        inset 3px 0 4px -2px rgba(0, 0, 0, 0.18);
}

/* ===== Hover: expand + rotate toward the viewer ===== */
.joni-books-grid-wrap .joni-grid-card:hover .joni-book-3d,
.joni-books-grid-wrap .joni-grid-card:focus-visible .joni-book-3d,
.joni-books-carousel-section .joni-carousel-card:hover .joni-book-3d,
.joni-books-carousel-section .joni-carousel-card:focus-visible .joni-book-3d {
    transform: rotateY(-6deg) scale(1.08) translateY(-8px);
    filter: drop-shadow(22px 22px 30px rgba(0, 0, 0, 0.34));
}

@media (prefers-reduced-motion: reduce) {
    .joni-book-3d { transition: none !important; }
    .joni-books-grid-wrap .joni-grid-card:hover .joni-book-3d,
    .joni-books-carousel-section .joni-carousel-card:hover .joni-book-3d {
        transform: rotateY(-14deg);
        filter: drop-shadow(16px 14px 20px rgba(0, 0, 0, 0.28));
    }
}
@media (max-width: 600px) {
    .joni-book-3d { transform: rotateY(-13deg); }
    .joni-3d-scene { padding: 12px 10px 20px !important; }
    .joni-book-3d .joni-book-3d-spine { width: 18px; }
    /* pages keep their page-count width, just scaled down a touch */
    .joni-book-3d .joni-book-3d-pages { width: calc(var(--joni-pages-w, 16px) * 0.8); }
}
CSS;
}

/* Emit the 3D book CSS in <head> so it applies on every page that renders a book,
 * independent of shortcode order (the carousel and grid each call it too; the
 * static guard in joni_3d_book_css() prevents duplicate output). */
add_action( 'wp_head', 'joni_3d_book_css_head', 998 );
function joni_3d_book_css_head() {
    $css = joni_3d_book_css();
    if ( $css ) {
        echo '<style id="joni-3d-book-css">' . $css . '</style>';
    }
}

/* ===== Page-count -> thickness helpers, appended to joni-books.php =====
 * Mapping (option B): real-world range ~100-500 pages -> 10px..30px edge.
 *   thickness(166)=13.3px  (197)=19.8px  (210)=22.6px  (212)=25px  blank=17px
 * Clamped, so a 2000-page outlier renders 30px, not a broken 120px slab.
 */
function joni_book_edge_px( $pages ) {
    $pages = (int) $pages;
    if ( $pages <= 0 ) {
        return 17; // default for unknown (e.g. an unpublished book)
    }
    /* Anchor to this catalog's real range so differences are actually visible.
     * A 100-500px anchor put 166..212 into only 2px of spread -- invisible.
     * 160pp -> 12px, 220pp -> 26px gives a clear 13.3px..25px spread on the
     * current books, while the outer 10..30 clamp keeps outliers sane. */
    $min_pages = 160;
    $max_pages = 220;
    $min_px    = 12;
    $max_px    = 26;
    if ( $pages <= $min_pages ) { return $min_px; }
    if ( $pages >= $max_pages ) { return $max_px; }
    $t = ( $pages - $min_pages ) / ( $max_pages - $min_pages );
    return round( $min_px + $t * ( $max_px - $min_px ), 1 );
}

/* A leaf ridge that scales with thickness: more pages = finer, denser lines. */
function joni_book_ridge_px( $pages ) {
    $pages = (int) $pages;
    if ( $pages <= 0 ) { $pages = 200; }
    // 166pp -> ~0.85px leaf, 500pp -> ~0.5px leaf; clamp for legibility
    $leaf = $pages / 200.0;
    $leaf = max( 0.55, min( 1.1, $leaf ) );
    return round( $leaf, 2 );
}

/* Style attrs for the pages element: width = computed thickness. */
function joni_book_pages_style( $pages ) {
    $edge  = joni_book_edge_px( $pages );
    $ridge = joni_book_ridge_px( $pages );
    $lines = (int) round( $edge / $ridge );
    if ( $lines < 4 ) { $lines = 4; }
    $dark = round( $edge * 0.10, 1 );
    $wide = round( $edge * 0.22, 1 );
    // Rounded thickness so a 166-page book is visibly thinner than a 212-page one.
    return sprintf(
        '--joni-pages-w:%spx; --joni-leaf:%spx; --joni-lines:%d; --joni-pl:0; --joni-pr:%spx; --joni-pshadow:inset -%spx 0 %spx rgba(0,0,0,0.16);',
        $edge, $ridge, $lines, $wide, $dark, $dark
    );
}

/* Human-readable page count for the card meta line. */
function joni_book_pages_label( $pages ) {
    $pages = (int) $pages;
    if ( $pages <= 0 ) { return ''; }
    return $pages . ' pages';
}