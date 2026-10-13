<?php
/**
 * Template Name: Events Category Archive
 * Clean, modern layout for Events listing inspired by Elisabeth Elliot style.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // Rendered inside WordPress only — block direct web access.
}

get_header();
?>

<style>
/* Events Archive Styles */
.joni-events-archive-page {
    background-color: #fbfbfb;
    padding: 40px 20px 80px;
    font-family: inherit;
    color: #2d3748;
}

.joni-events-container {
    max-width: 1060px;
    margin: 0 auto;
}

/* Breadcrumbs */
.joni-events-breadcrumbs {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 30px;
    padding-bottom: 15px;
    border-bottom: 1px solid #edf2f7;
}

.joni-events-breadcrumbs a {
    color: #4a5568;
    text-decoration: none;
    transition: color 0.2s;
}

.joni-events-breadcrumbs a:hover {
    color: #2b6cb0;
}

.joni-events-breadcrumbs .sep {
    color: #a0aec0;
    font-size: 0.8rem;
}

.joni-events-breadcrumbs .current {
    color: #1a202c;
    font-weight: 600;
}

/* Header */
.joni-events-header-box {
    text-align: center;
    margin-bottom: 45px;
}

.joni-events-page-title {
    font-size: 2.5rem;
    font-weight: 800;
    color: #1a202c;
    margin: 0 0 12px;
    letter-spacing: -0.02em;
}

.joni-events-page-sub {
    font-size: 1.15rem;
    color: #4a5568;
    max-width: 680px;
    margin: 0 auto;
    line-height: 1.6;
}

/* Events List / Grid */
.joni-events-list {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.joni-event-item-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 28px 32px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.05);
    border: 1px solid #edf2f7;
    display: grid;
    grid-template-columns: 100px 1fr auto;
    gap: 28px;
    align-items: center;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.joni-event-item-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 28px rgba(0,0,0,0.08);
}

@media (max-width: 768px) {
    .joni-event-item-card {
        grid-template-columns: 80px 1fr;
        gap: 18px;
        padding: 20px;
    }
    .joni-event-item-actions {
        grid-column: 1 / -1;
        margin-top: 10px;
    }
}

/* Date Box */
.joni-event-date-badge {
    background: #1a202c;
    color: #ffffff;
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 14px 8px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(26,32,44,0.15);
}

.joni-event-date-month {
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #90cdf4;
    line-height: 1;
    margin-bottom: 4px;
}

.joni-event-date-day {
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1;
}

/* Event Info */
.joni-event-item-info {
    display: flex;
    flex-direction: column;
}

.joni-event-item-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: #1a202c;
    margin: 0 0 8px;
    line-height: 1.3;
}

.joni-event-item-title a {
    color: #1a202c;
    text-decoration: none;
    transition: color 0.2s;
}

.joni-event-item-title a:hover {
    color: #3182ce;
}

.joni-event-item-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 0.92rem;
    color: #4a5568;
    margin-bottom: 8px;
}

.joni-event-item-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.joni-event-item-meta-item svg {
    color: #3182ce;
}

.joni-event-item-desc {
    font-size: 0.96rem;
    color: #718096;
    margin: 0;
    line-height: 1.5;
}

/* Action Buttons */
.joni-event-item-actions {
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-end;
}

@media (max-width: 768px) {
    .joni-event-item-actions {
        flex-direction: row;
        align-items: center;
    }
}

.joni-btn-card-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 18px;
    font-size: 0.9rem;
    font-weight: 600;
    border-radius: 6px;
    text-decoration: none;
    white-space: nowrap;
    transition: all 0.2s ease;
}

.joni-btn-card-primary {
    background-color: #1a202c;
    color: #ffffff !important;
}

.joni-btn-card-primary:hover {
    background-color: #3182ce;
}

.joni-btn-card-secondary {
    background-color: #ffffff;
    color: #2d3748 !important;
    border: 1px solid #cbd5e0;
}

.joni-btn-card-secondary:hover {
    background-color: #f7fafc;
    border-color: #a0aec0;
}
</style>

<div id="primary" class="content-area joni-events-archive-page">
    <div class="joni-events-container">

        <!-- Breadcrumbs -->
        <nav class="joni-events-breadcrumbs" aria-label="Breadcrumb">
            <a href="<?php echo esc_url( home_url( '/' ) ); ?>">Home</a>
            <span class="sep">&rsaquo;</span>
            <span class="current">Events</span>
        </nav>

        <div class="joni-events-header-box">
            <h1 class="joni-events-page-title">Author Events &amp; Appearances</h1>
            <p class="joni-events-page-sub">
                Join Dr. Joni Schwartz-Chaney for upcoming book readings, signings, and community discussions.
            </p>
        </div>

        <div class="joni-events-list">
            <?php
            // Resolve events by slug — 21 is staging's term ID and means nothing
            // on another install, where it silently queried a different category.
            $events_id = joni_category_id( 'events' );
            $events_args = array(
                'posts_per_page' => 20,
                'post_status'    => 'publish',
                'orderby'        => 'date',
                'order'          => 'DESC',
            );
            if ( $events_id ) {
                $events_args['cat'] = $events_id;
            } else {
                $events_args['post__in'] = array( 0 );
            }
            $events_query = new WP_Query( $events_args );

            if ( $events_query->have_posts() ) :
                while ( $events_query->have_posts() ) : $events_query->the_post();
                    $e_id = get_the_ID();
                    $e_date_str = get_post_meta( $e_id, '_event_date_formatted', true );
                    $e_time     = get_post_meta( $e_id, '_event_time', true );
                    $e_venue    = get_post_meta( $e_id, '_event_venue', true );
                    $e_address  = get_post_meta( $e_id, '_event_address', true );
                    $e_month    = get_post_meta( $e_id, '_event_month', true );
                    $e_day      = get_post_meta( $e_id, '_event_day', true );

                    if ( empty( $e_month ) || empty( $e_day ) ) {
                        $e_month = get_the_date( 'M' );
                        $e_day   = get_the_date( 'd' );
                    }

                    if ( empty( $e_venue ) ) {
                        $title = get_the_title();
                        if ( strpos( $title, '—' ) !== false ) {
                            $parts = explode( '—', $title );
                            $e_venue = trim( $parts[0] );
                        } else {
                            $e_venue = $title;
                        }
                    }

                    $maps_url = ! empty( $e_address )
                        ? 'https://www.google.com/maps/search/?api=1&query=' . urlencode( $e_venue . ' ' . $e_address )
                        : '';
            ?>
                    <article class="joni-event-item-card">
                        <!-- Date Badge -->
                        <div class="joni-event-date-badge">
                            <span class="joni-event-date-month"><?php echo esc_html( $e_month ); ?></span>
                            <span class="joni-event-date-day"><?php echo esc_html( $e_day ); ?></span>
                        </div>

                        <!-- Info -->
                        <div class="joni-event-item-info">
                            <h2 class="joni-event-item-title">
                                <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                            </h2>

                            <div class="joni-event-item-meta">
                                <?php if ( ! empty( $e_time ) ) : ?>
                                    <span class="joni-event-item-meta-item">
                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                                        <?php echo esc_html( $e_time ); ?>
                                    </span>
                                <?php endif; ?>

                                <?php if ( ! empty( $e_address ) ) : ?>
                                    <span class="joni-event-item-meta-item">
                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                                        <?php echo esc_html( $e_address ); ?>
                                    </span>
                                <?php endif; ?>
                            </div>

                            <p class="joni-event-item-desc">
                                <?php echo wp_trim_words( get_the_excerpt(), 25 ); ?>
                            </p>
                        </div>

                        <!-- Actions -->
                        <div class="joni-event-item-actions">
                            <a href="<?php the_permalink(); ?>" class="joni-btn-card-action joni-btn-card-primary">
                                <span>Event Details</span>
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
                            </a>
                            <?php if ( ! empty( $maps_url ) ) : ?>
                                <a href="<?php echo esc_url( $maps_url ); ?>" target="_blank" rel="noopener noreferrer" class="joni-btn-card-action joni-btn-card-secondary">
                                    Directions
                                </a>
                            <?php endif; ?>
                        </div>
                    </article>
            <?php
                endwhile;
                wp_reset_postdata();
            else :
            ?>
                <p>No upcoming events found.</p>
            <?php endif; ?>
        </div>

    </div>
</div>

<?php
get_footer();
