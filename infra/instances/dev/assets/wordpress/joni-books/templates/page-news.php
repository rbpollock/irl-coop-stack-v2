<?php
/**
 * Template Name: News Page (news cards + events sidebar)
 * Full-width news cards with an events side panel.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // Rendered inside WordPress only — block direct web access.
}

get_header();
?>

<style>
.joni-news-page {
    background-color: #fbfbfb;
    padding: 48px 24px 90px;
    font-family: inherit;
    color: #2d3748;
}
.joni-news-layout {
    max-width: 1200px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 40px;
    align-items: start;
}
@media (max-width: 900px) {
    .joni-news-layout {
        grid-template-columns: 1fr;
    }
}
/* Page heading */
.joni-news-page-head {
    margin-bottom: 34px;
}
.joni-news-page-title {
    font-size: 2.4rem;
    font-weight: 800;
    color: #1a202c;
    margin: 0 0 10px;
    letter-spacing: -0.02em;
}
.joni-news-page-sub {
    font-size: 1.1rem;
    color: #4a5568;
    margin: 0;
    max-width: 680px;
    line-height: 1.6;
}
/* News cards (full-width) */
.joni-news-card {
    background: #ffffff;
    border-radius: 16px;
    border: 1px solid #edf2f7;
    padding: 32px 34px;
    box-shadow: 0 10px 30px -5px rgba(16, 33, 54, 0.07), 0 1px 3px rgba(16, 33, 54, 0.04);
    position: relative;
    overflow: hidden;
    margin-bottom: 26px;
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
}
.joni-news-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 24px 45px -10px rgba(16, 33, 54, 0.16), 0 4px 10px rgba(16, 33, 54, 0.06);
    border-color: #cbd5e0;
}
.joni-news-card-meta {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
}
.joni-news-cat {
    display: inline-flex;
    padding: 4px 12px;
    background: #ebf8ff;
    color: #2b6cb0;
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-radius: 999px;
    border: 1px solid #bee3f8;
}
.joni-news-cat.joni-cat-reviews {
    background: #faf5ff;
    color: #6b46c1;
    border-color: #e9d8fd;
}
.joni-news-date {
    font-size: 0.85rem;
    font-weight: 600;
    color: #a0aec0;
}
.joni-news-card-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #102136;
    margin: 0 0 12px;
    line-height: 1.3;
    letter-spacing: -0.01em;
}
.joni-news-card-title a {
    color: inherit;
    text-decoration: none;
    transition: color 0.2s;
}
.joni-news-card-title a:hover {
    color: #3182ce;
}
.joni-news-card-excerpt {
    font-size: 1.02rem;
    color: #718096;
    line-height: 1.65;
    margin: 0 0 16px;
}
.joni-news-card-readmore {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #2b6cb0;
    text-decoration: none;
}
.joni-news-card-readmore:hover {
    color: #102136;
}
/* Sidebar */
.joni-news-sidebar {
    background: #ffffff;
    border-radius: 16px;
    border: 1px solid #edf2f7;
    padding: 28px;
    box-shadow: 0 10px 30px -5px rgba(16, 33, 54, 0.07);
    position: sticky;
    top: 100px;
}
.joni-sidebar-head {
    font-size: 1.15rem;
    font-weight: 800;
    color: #102136;
    margin: 0 0 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid #edf2f7;
}
.joni-sidebar-event {
    display: flex;
    gap: 14px;
    padding: 14px 0;
    border-bottom: 1px solid #f0f4f8;
}
.joni-sidebar-event:last-of-type {
    border-bottom: none;
}
.joni-sidebar-event-date {
    flex-shrink: 0;
    width: 46px;
    height: 46px;
    background: #102136;
    color: #ffffff;
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    line-height: 1;
}
.joni-sidebar-event-month {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #90cdf4;
    margin-bottom: 2px;
}
.joni-sidebar-event-day {
    font-size: 1.05rem;
}
.joni-sidebar-event-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1a202c;
    line-height: 1.35;
    margin: 0;
}
.joni-sidebar-event-title a {
    color: inherit;
    text-decoration: none;
}
.joni-sidebar-event-title a:hover {
    color: #3182ce;
}
.joni-sidebar-event-venue {
    font-size: 0.82rem;
    color: #718096;
    margin-top: 3px;
}
.joni-sidebar-all {
    display: inline-flex;
    margin-top: 18px;
    font-size: 0.9rem;
    font-weight: 600;
    color: #2b6cb0;
    text-decoration: none;
}
.joni-sidebar-all:hover {
    color: #102136;
}
</style>

<div class="joni-news-page">
    <div class="joni-news-layout">

        <div class="joni-news-main">
            <div class="joni-news-page-head">
                <h1 class="joni-news-page-title">News</h1>
                <p class="joni-news-page-sub">Latest updates, announcements, and reflections from Joni.</p>
            </div>

            <?php
            // Resolve by SLUG, never by term ID: term IDs are per-site and the
            // staging IDs (13 = News, 20 = Reviews, 21 = Events) do not exist on
            // any other install. Hardcoding them made this loop query unrelated
            // categories and render an empty news page.
            $news_ids = joni_category_ids( array( 'news', 'reviews' ) );
            $news_args = array(
                'posts_per_page' => 12,
                'post_status'    => 'publish',
                'orderby'        => 'date',
                'order'          => 'DESC',
            );
            if ( $news_ids ) {
                $news_args['category__in'] = $news_ids;
            } else {
                $news_args['post__in'] = array( 0 ); // no News/Reviews terms -> show nothing
            }
            $news_query = new WP_Query( $news_args );

            if ( $news_query->have_posts() ) :
                while ( $news_query->have_posts() ) : $news_query->the_post();
                    $cat_name = 'News';
                    $cat_slug = 'news';
                    $cats = get_the_category();
                    if ( ! empty( $cats ) ) {
                        foreach ( $cats as $c ) {
                            if ( in_array( $c->slug, array( 'news', 'reviews' ), true ) ) {
                                $cat_name = $c->name;
                                $cat_slug = $c->slug;
                                break;
                            }
                        }
                    }
                    $excerpt = trim( wp_strip_all_tags( get_the_excerpt() ) );
                    if ( empty( $excerpt ) || preg_match( '/^https?:\/\/\S+$/', $excerpt ) ) {
                        $excerpt = trim( wp_strip_all_tags( get_the_content() ) );
                    }
                    if ( preg_match( '/^https?:\/\/\S+$/', $excerpt ) ) {
                        $excerpt = '';
                    }
                    $excerpt = wp_trim_words( $excerpt, 32, '…' );
                ?>
                    <article class="joni-news-card">
                        <div class="joni-news-card-meta">
                            <span class="joni-news-cat joni-cat-<?php echo esc_attr( $cat_slug ); ?>"><?php echo esc_html( $cat_name ); ?></span>
                            <span class="joni-news-date"><?php echo get_the_date(); ?></span>
                        </div>
                        <h2 class="joni-news-card-title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h2>
                        <?php if ( ! empty( $excerpt ) ) : ?>
                            <p class="joni-news-card-excerpt"><?php echo esc_html( $excerpt ); ?></p>
                        <?php endif; ?>
                        <a class="joni-news-card-readmore" href="<?php the_permalink(); ?>">Read more &rarr;</a>
                    </article>
                <?php
                endwhile;
                wp_reset_postdata();
            else :
            ?>
                <p>No news posts yet.</p>
            <?php endif; ?>
        </div>

        <aside class="joni-news-sidebar">
            <h2 class="joni-sidebar-head">Upcoming Events</h2>
            <?php
            $events_id = joni_category_id( 'events' ); // by slug: 21 is staging's ID only
            $events_args = array(
                'posts_per_page' => 5,
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
                    $e_month = get_post_meta( $e_id, '_event_month', true );
                    $e_day   = get_post_meta( $e_id, '_event_day', true );
                    $e_venue = get_post_meta( $e_id, '_event_venue', true );
                    if ( empty( $e_month ) || empty( $e_day ) ) {
                        $e_month = get_the_date( 'M' );
                        $e_day   = get_the_date( 'd' );
                    }
                    if ( empty( $e_venue ) ) {
                        $title = get_the_title();
                        $e_venue = ( strpos( $title, '—' ) !== false )
                            ? trim( explode( '—', $title )[0] )
                            : $title;
                    }
                ?>
                    <div class="joni-sidebar-event">
                        <div class="joni-sidebar-event-date">
                            <span class="joni-sidebar-event-month"><?php echo esc_html( $e_month ); ?></span>
                            <span class="joni-sidebar-event-day"><?php echo esc_html( $e_day ); ?></span>
                        </div>
                        <div>
                            <h3 class="joni-sidebar-event-title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h3>
                            <div class="joni-sidebar-event-venue"><?php echo esc_html( $e_venue ); ?></div>
                        </div>
                    </div>
                <?php
                endwhile;
                wp_reset_postdata();
            else :
            ?>
                <p>No upcoming events.</p>
            <?php endif; ?>
            <a class="joni-sidebar-all" href="<?php echo esc_url( home_url( '/category/events/' ) ); ?>">View all events &rarr;</a>
        </aside>

    </div>
</div>

<?php
get_footer();
