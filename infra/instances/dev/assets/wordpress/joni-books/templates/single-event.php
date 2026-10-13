<?php
/**
 * Template Name: Event Detail Page
 * Clean, modern layout for Events (category 21) inspired by the Elisabeth Elliot book pages.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // Rendered inside WordPress only — block direct web access.
}

get_header();

while ( have_posts() ) : the_post();
    $event_id = get_the_ID();

    $event_date_str = get_post_meta( $event_id, '_event_date_formatted', true );
    $event_time     = get_post_meta( $event_id, '_event_time', true );
    $event_venue    = get_post_meta( $event_id, '_event_venue', true );
    $event_address  = get_post_meta( $event_id, '_event_address', true );
    $event_month    = get_post_meta( $event_id, '_event_month', true );
    $event_day      = get_post_meta( $event_id, '_event_day', true );

    // Fallback parsing if meta not set
    if ( empty( $event_venue ) ) {
        $title = get_the_title();
        if ( strpos( $title, '—' ) !== false ) {
            $parts = explode( '—', $title );
            $event_venue = trim( $parts[0] );
            if ( empty( $event_time ) && isset( $parts[1] ) ) {
                $time_parts = explode( ',', $parts[1] );
                if ( isset( $time_parts[1] ) ) {
                    $event_time = trim( $time_parts[1] );
                }
            }
        } else {
            $event_venue = $title;
        }
    }

    $maps_url = ! empty( $event_address )
        ? 'https://www.google.com/maps/search/?api=1&query=' . urlencode( $event_venue . ' ' . $event_address )
        : '';
?>

<style>
/* Event Detail Page Styles */
.joni-event-page {
    background-color: #fbfbfb;
    padding: 40px 20px 80px;
    font-family: inherit;
    color: #2d3748;
}

.joni-event-container {
    max-width: 900px;
    margin: 0 auto;
}

/* Breadcrumbs */
.joni-event-breadcrumbs {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 30px;
    padding-bottom: 15px;
    border-bottom: 1px solid #edf2f7;
}

.joni-event-breadcrumbs a {
    color: #4a5568;
    text-decoration: none;
    transition: color 0.2s;
}

.joni-event-breadcrumbs a:hover {
    color: #2b6cb0;
}

.joni-event-breadcrumbs .sep {
    color: #a0aec0;
    font-size: 0.8rem;
}

.joni-event-breadcrumbs .current {
    color: #1a202c;
    font-weight: 600;
}

/* Event Card */
.joni-event-card-main {
    background: #ffffff;
    border-radius: 12px;
    padding: 48px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.05);
    border: 1px solid #edf2f7;
}

@media (max-width: 600px) {
    .joni-event-card-main {
        padding: 24px 20px;
    }
}

.joni-event-badge {
    display: inline-block;
    padding: 5px 14px;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background-color: #ebf4ff;
    color: #2b6cb0;
    border-radius: 999px;
    margin-bottom: 16px;
}

.joni-event-title {
    font-size: 2.2rem;
    font-weight: 700;
    line-height: 1.25;
    color: #1a202c;
    margin: 0 0 24px 0;
    letter-spacing: -0.02em;
}

/* Date & Location Highlight Box */
.joni-event-meta-box {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    background-color: #f7fafc;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #3182ce;
    border-radius: 0 8px 8px 0;
    padding: 24px;
    margin-bottom: 36px;
}

.joni-event-meta-col {
    display: flex;
    align-items: flex-start;
    gap: 14px;
}

.joni-event-meta-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: #ebf4ff;
    color: #3182ce;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.joni-event-meta-info {
    display: flex;
    flex-direction: column;
}

.joni-event-meta-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #718096;
    margin-bottom: 2px;
}

.joni-event-meta-val-primary {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1a202c;
}

.joni-event-meta-val-secondary {
    font-size: 0.92rem;
    color: #4a5568;
    margin-top: 2px;
}

/* Event Content / Description */
.joni-event-content {
    font-size: 1.1rem;
    line-height: 1.8;
    color: #374151;
    margin-bottom: 40px;
}

.joni-event-content p {
    margin-bottom: 1.2em;
}

.joni-event-content ul {
    list-style: none;
    padding: 0;
    margin: 20px 0;
}

.joni-event-content li {
    padding: 8px 0;
    border-bottom: 1px solid #f0f4f8;
}

/* Actions */
.joni-event-actions-box {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    padding-top: 28px;
    border-top: 2px dashed #edf2f7;
    margin-top: 30px;
}

.joni-btn-event {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.95rem;
    text-decoration: none;
    transition: all 0.2s ease;
}

.joni-btn-event-primary {
    background-color: #3182ce;
    color: #ffffff !important;
}

.joni-btn-event-primary:hover {
    background-color: #2b6cb0;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(49, 130, 206, 0.35);
}

.joni-btn-event-secondary {
    background-color: #ffffff;
    color: #2d3748 !important;
    border: 1px solid #cbd5e0;
}

.joni-btn-event-secondary:hover {
    background-color: #f7fafc;
    border-color: #a0aec0;
    transform: translateY(-2px);
}

.joni-event-back-nav {
    margin-top: 40px;
    padding-top: 20px;
}

.joni-event-back-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #4a5568;
    text-decoration: none;
    font-size: 0.95rem;
    font-weight: 500;
    transition: color 0.2s;
}

.joni-event-back-link:hover {
    color: #3182ce;
}
</style>

<div id="primary" class="content-area joni-event-page">
    <div class="joni-event-container">

        <!-- Breadcrumbs -->
        <nav class="joni-event-breadcrumbs" aria-label="Breadcrumb">
            <a href="<?php echo esc_url( home_url( '/' ) ); ?>">Home</a>
            <span class="sep">&rsaquo;</span>
            <a href="<?php echo esc_url( home_url( '/category/events/' ) ); ?>">Events</a>
            <span class="sep">&rsaquo;</span>
            <span class="current"><?php the_title(); ?></span>
        </nav>

        <div class="joni-event-card-main">
            <span class="joni-event-badge">Author Event</span>
            <h1 class="joni-event-title"><?php the_title(); ?></h1>

            <!-- Meta Box (Date, Time, Venue, Location) -->
            <div class="joni-event-meta-box">
                <div class="joni-event-meta-col">
                    <div class="joni-event-meta-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                    </div>
                    <div class="joni-event-meta-info">
                        <span class="joni-event-meta-label">Date &amp; Time</span>
                        <span class="joni-event-meta-val-primary"><?php echo esc_html( $event_date_str ?: 'Upcoming Date' ); ?></span>
                        <?php if ( ! empty( $event_time ) ) : ?>
                            <span class="joni-event-meta-val-secondary"><?php echo esc_html( $event_time ); ?></span>
                        <?php endif; ?>
                    </div>
                </div>

                <div class="joni-event-meta-col">
                    <div class="joni-event-meta-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    </div>
                    <div class="joni-event-meta-info">
                        <span class="joni-event-meta-label">Location</span>
                        <span class="joni-event-meta-val-primary"><?php echo esc_html( $event_venue ); ?></span>
                        <?php if ( ! empty( $event_address ) ) : ?>
                            <span class="joni-event-meta-val-secondary"><?php echo esc_html( $event_address ); ?></span>
                        <?php endif; ?>
                    </div>
                </div>
            </div>

            <!-- Content -->
            <div class="joni-event-content">
                <?php the_content(); ?>
            </div>

            <!-- Action Buttons -->
            <div class="joni-event-actions-box">
                <?php if ( ! empty( $maps_url ) ) : ?>
                    <a href="<?php echo esc_url( $maps_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-btn-event joni-btn-event-primary">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>
                        Get Directions
                    </a>
                <?php endif; ?>
                
                <a href="<?php echo esc_url( home_url( '/books/' ) ); ?>" class="joni-btn-event joni-btn-event-secondary">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                    Explore Joni's Books
                </a>
            </div>

            <div class="joni-event-back-nav">
                <a href="<?php echo esc_url( home_url( '/category/events/' ) ); ?>" class="joni-event-back-link">
                    &larr; View All Events
                </a>
            </div>

        </div>
    </div>
</div>

<?php
endwhile;

get_footer();
