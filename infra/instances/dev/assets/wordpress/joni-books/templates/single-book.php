<?php
/**
 * Template Name: Book Detail Page
 * Template for displaying single Book CPT items.
 * Clean, modern layout inspired by Elisabeth Elliot's book pages.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // Rendered inside WordPress only — block direct web access.
}

get_header();

while ( have_posts() ) : the_post();
    $book_id = get_the_ID();
    
    // Meta values
    $author = get_post_meta( $book_id, '_book_author', true );
    if ( empty( $author ) ) {
        $author = 'Dr. Joni Schwartz-Chaney';
    }
    $subtitle = get_post_meta( $book_id, '_book_subtitle', true );
    $publisher = get_post_meta( $book_id, '_book_publisher', true );
    $pub_year = get_post_meta( $book_id, '_book_pub_year', true );
    $isbn = get_post_meta( $book_id, '_book_isbn', true );
    $amazon_url = get_post_meta( $book_id, '_book_amazon_url', true );
    $publisher_url = get_post_meta( $book_id, '_book_publisher_url', true );
    $retailer_url = get_post_meta( $book_id, '_book_retailer_url', true );
    $retailer_label = get_post_meta( $book_id, '_book_retailer_label', true ) ?: 'Barnes & Noble';
    
    // Taxonomy terms
    $terms = get_the_terms( $book_id, 'book_category' );
    $has_cover = has_post_thumbnail();
    $cover_url = $has_cover ? get_the_post_thumbnail_url( $book_id, 'large' ) : '';
?>

<style>
/* Book Detail Page Styles */
.joni-book-page {
    background-color: #fbfbfb;
    padding: 40px 20px 80px;
    font-family: inherit;
    color: #2d3748;
}

.joni-book-container {
    max-width: 1120px;
    margin: 0 auto;
}

/* Breadcrumbs */
.joni-book-breadcrumbs {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 35px;
    padding-bottom: 15px;
    border-bottom: 1px solid #edf2f7;
}

.joni-book-breadcrumbs a {
    color: #4a5568;
    text-decoration: none;
    transition: color 0.2s;
}

.joni-book-breadcrumbs a:hover {
    color: #2b6cb0;
}

.joni-book-breadcrumbs .sep {
    color: #a0aec0;
    font-size: 0.8rem;
}

.joni-book-breadcrumbs .current {
    color: #1a202c;
    font-weight: 600;
}

/* Main Grid */
.joni-book-grid {
    display: grid;
    grid-template-columns: 340px 1fr;
    gap: 55px;
    align-items: start;
}

@media (max-width: 880px) {
    .joni-book-grid {
        grid-template-columns: 1fr;
        gap: 35px;
    }
}

/* Cover Column */
.joni-book-cover-col {
    position: sticky;
    top: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.joni-book-cover-wrapper {
    width: 100%;
    max-width: 340px;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 20px 40px -15px rgba(0,0,0,0.22), 0 0 1px rgba(0,0,0,0.1);
    background: #ffffff;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.joni-book-cover-wrapper:hover {
    transform: translateY(-4px);
    box-shadow: 0 26px 48px -15px rgba(0,0,0,0.28), 0 0 1px rgba(0,0,0,0.12);
}

.joni-book-cover-img {
    width: 100%;
    height: auto;
    display: block;
    object-fit: cover;
}

.joni-book-cover-placeholder {
    width: 100%;
    aspect-ratio: 1 / 1.5;
    background: linear-gradient(135deg, #4a5568, #2d3748);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    font-weight: 600;
    font-size: 1.1rem;
    padding: 20px;
    text-align: center;
}

/* Categories / Badge */
.joni-book-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 18px;
    justify-content: center;
}

.joni-book-badge {
    display: inline-block;
    padding: 5px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background-color: #ebf4ff;
    color: #2b6cb0;
    border-radius: 999px;
    text-decoration: none;
    transition: background 0.2s;
}

.joni-book-badge:hover {
    background-color: #bee3f8;
    color: #2c5282;
}

/* Details Column */
.joni-book-details-col {
    background: #ffffff;
    padding: 42px 48px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.04);
    border: 1px solid #edf2f7;
}

@media (max-width: 600px) {
    .joni-book-details-col {
        padding: 24px 20px;
    }
}

.joni-book-title {
    font-size: 2.3rem;
    font-weight: 700;
    line-height: 1.25;
    color: #1a202c;
    margin: 0 0 10px 0;
    letter-spacing: -0.02em;
}

.joni-book-subtitle {
    font-size: 1.25rem;
    color: #4a5568;
    font-weight: 500;
    margin: 0 0 16px 0;
    line-height: 1.4;
}

.joni-book-author {
    font-size: 1.1rem;
    color: #718096;
    margin-bottom: 24px;
    font-style: italic;
}

.joni-book-author strong {
    color: #2d3748;
    font-style: normal;
}

/* Metadata Card */
.joni-book-meta-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    padding: 16px 20px;
    background-color: #f7fafc;
    border-left: 4px solid #3182ce;
    border-radius: 0 8px 8px 0;
    margin-bottom: 30px;
    font-size: 0.92rem;
}

.joni-book-meta-item {
    display: flex;
    flex-direction: column;
}

.joni-book-meta-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #a0aec0;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}

.joni-book-meta-value {
    color: #2d3748;
    font-weight: 600;
}

/* Book Description / Content */
.joni-book-synopsis {
    font-size: 1.05rem;
    line-height: 1.8;
    color: #374151;
    margin-bottom: 40px;
}

.joni-book-synopsis p {
    margin-bottom: 1.2em;
}

.joni-book-synopsis p:last-child {
    margin-bottom: 0;
}

/* Purchase Section (Elisabeth Elliot style) */
.joni-book-purchase-box {
    margin-top: 36px;
    padding-top: 30px;
    border-top: 2px dashed #edf2f7;
}

.joni-book-purchase-heading {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1a202c;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.joni-book-purchase-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
}

.joni-btn-retailer {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.95rem;
    text-decoration: none;
    transition: all 0.2s ease;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

.joni-btn-amazon {
    background-color: #232f3e;
    color: #ffffff !important;
}

.joni-btn-amazon:hover {
    background-color: #131921;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.joni-btn-publisher {
    background-color: #3182ce;
    color: #ffffff !important;
}

.joni-btn-publisher:hover {
    background-color: #2b6cb0;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(49, 130, 206, 0.35);
}

.joni-btn-other {
    background-color: #ffffff;
    color: #2d3748 !important;
    border: 1px solid #cbd5e0;
}

.joni-btn-other:hover {
    background-color: #f7fafc;
    border-color: #a0aec0;
    transform: translateY(-2px);
}

/* Back Link */
.joni-book-back-nav {
    margin-top: 40px;
    padding-top: 20px;
}

.joni-book-back-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #4a5568;
    text-decoration: none;
    font-size: 0.95rem;
    font-weight: 500;
    transition: color 0.2s;
}

.joni-book-back-link:hover {
    color: #3182ce;
}
</style>

<div id="primary" class="content-area joni-book-page">
    <div class="joni-book-container">
        
        <!-- Breadcrumbs (Elisabeth Elliot style) -->
        <nav class="joni-book-breadcrumbs" aria-label="Breadcrumb">
            <a href="<?php echo esc_url( home_url( '/' ) ); ?>">Home</a>
            <span class="sep">&rsaquo;</span>
            <a href="<?php echo esc_url( home_url( '/books/' ) ); ?>">Books</a>
            <span class="sep">&rsaquo;</span>
            <span class="current"><?php the_title(); ?></span>
        </nav>

        <div class="joni-book-grid">
            
            <!-- Left: Book Cover & Badges -->
            <div class="joni-book-cover-col">
                <div class="joni-book-cover-wrapper">
                    <?php if ( $has_cover ) : ?>
                        <img src="<?php echo esc_url( $cover_url ); ?>" alt="<?php the_title_attribute(); ?>" class="joni-book-cover-img" />
                    <?php else : ?>
                        <div class="joni-book-cover-placeholder">
                            <?php the_title(); ?>
                        </div>
                    <?php endif; ?>
                </div>

                <?php if ( ! empty( $terms ) && ! is_wp_error( $terms ) ) : ?>
                    <div class="joni-book-badges">
                        <?php foreach ( $terms as $term ) : ?>
                            <span class="joni-book-badge"><?php echo esc_html( $term->name ); ?></span>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
            </div>

            <!-- Right: Details, Metadata, Description & Retail Links -->
            <div class="joni-book-details-col">
                <h1 class="joni-book-title"><?php the_title(); ?></h1>
                
                <?php if ( ! empty( $subtitle ) ) : ?>
                    <div class="joni-book-subtitle"><?php echo esc_html( $subtitle ); ?></div>
                <?php endif; ?>

                <div class="joni-book-author">
                    by <strong><?php echo esc_html( $author ); ?></strong>
                </div>

                <!-- Metadata Row -->
                <?php if ( ! empty( $publisher ) || ! empty( $pub_year ) || ! empty( $isbn ) ) : ?>
                    <div class="joni-book-meta-bar">
                        <?php if ( ! empty( $publisher ) ) : ?>
                            <div class="joni-book-meta-item">
                                <span class="joni-book-meta-label">Publisher</span>
                                <span class="joni-book-meta-value"><?php echo esc_html( $publisher ); ?></span>
                            </div>
                        <?php endif; ?>

                        <?php if ( ! empty( $pub_year ) ) : ?>
                            <div class="joni-book-meta-item">
                                <span class="joni-book-meta-label">Year</span>
                                <span class="joni-book-meta-value"><?php echo esc_html( $pub_year ); ?></span>
                            </div>
                        <?php endif; ?>

                        <?php if ( ! empty( $isbn ) ) : ?>
                            <div class="joni-book-meta-item">
                                <span class="joni-book-meta-label">ISBN</span>
                                <span class="joni-book-meta-value"><?php echo esc_html( $isbn ); ?></span>
                            </div>
                        <?php endif; ?>
                    </div>
                <?php endif; ?>

                <!-- Book Synopsis / Full Content -->
                <div class="joni-book-synopsis">
                    <?php the_content(); ?>
                </div>

                <!-- Purchase from favorite retailer section (Elisabeth Elliot style) -->
                <?php if ( ! empty( $amazon_url ) || ! empty( $publisher_url ) || ! empty( $retailer_url ) ) : ?>
                    <div class="joni-book-purchase-box">
                        <div class="joni-book-purchase-heading">
                            <span>Purchase from your favorite retailer</span>
                        </div>
                        <div class="joni-book-purchase-buttons">
                            <?php if ( ! empty( $amazon_url ) ) : ?>
                                <a href="<?php echo esc_url( $amazon_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-btn-retailer joni-btn-amazon">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M13.882 17.125c-2.317 1.705-5.69 2.6-8.582 2.6-4.048 0-7.7-1.57-10.457-4.205-.216-.206-.023-.487.238-.328 3.03 1.838 6.757 2.943 10.59 2.943 2.568 0 5.405-.623 7.973-1.91.389-.196.696.257.238.9zm1.258-.787c-.297-.384-.595-1.127-.595-1.127s.745.247 1.488.247c1.378 0 2.213-.807 2.213-2.015 0-1.077-.663-1.896-1.815-1.896-1.39 0-2.32 1.054-2.32 2.508 0 .848.337 1.62.912 2.115-.467.098-1.01.148-1.554.148-1.874 0-3.626-.594-4.887-1.637-.179-.148-.052-.377.156-.277 1.135.547 2.585.873 4.093.873.344 0 .685-.018 1.02-.054-.368-.466-.582-1.053-.582-1.748 0-1.854 1.34-3.328 3.303-3.328 1.62 0 2.766 1.076 2.766 2.628 0 1.93-1.388 3.256-3.418 3.256-.298 0-.582-.03-.847-.09zM21.75 18.25c-.274-.216-.58-.337-.887-.337-.417 0-.825.216-1.076.602-.275.424-.26 1.002.04 1.442.275.405.748.644 1.222.644.405 0 .807-.17 1.062-.486.297-.37.337-.91.136-1.428-.118-.17-.282-.32-.497-.437z"/></svg>
                                    Buy on Amazon
                                </a>
                            <?php endif; ?>

                            <?php if ( ! empty( $publisher_url ) ) : ?>
                                <a href="<?php echo esc_url( $publisher_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-btn-retailer joni-btn-publisher">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                                    Order from <?php echo ! empty( $publisher ) ? esc_html( $publisher ) : 'Publisher'; ?>
                                </a>
                            <?php endif; ?>

                            <?php if ( ! empty( $retailer_url ) ) : ?>
                                <a href="<?php echo esc_url( $retailer_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-btn-retailer joni-btn-other">
                                    <?php echo esc_html( $retailer_label ); ?>
                                </a>
                            <?php endif; ?>
                        </div>
                    </div>
                <?php endif; ?>

                <div class="joni-book-back-nav">
                    <a href="<?php echo esc_url( home_url( '/books/' ) ); ?>" class="joni-book-back-link">
                        &larr; View All Books by Joni
                    </a>
                </div>

            </div>

        </div>

    </div>
</div>

<?php
endwhile;

get_footer();
