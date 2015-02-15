function wpf_cache_regen() {
    wpf_indicator_on('#wpf_cache_regen');
    jQuery.ajax({
        type: 'POST',
        url: ajaxurl,
        async: true,
        data: {action:'wpf_cache_regen', security:wpf_nonce},
        complete: function (xhr, text) {
            wpf_indicator_off(
                '#wpf_cache_regen',
                (xhr.statusText == 'error' || xhr.responseText.indexOf('FAIL ') == 0),
                (typeof(xhr.responseText) !== 'undefined' && xhr.responseText ? xhr.responseText : xhr.statusText)
            );
        }
    });
}


function wpf_cache_stats() {
    jQuery('#wpf_cache_stats_data').hide();
    tbody = jQuery('#wpf_cache_stats_data tbody')
    tbody.empty();
    wpf_indicator_on('#wpf_cache_stats');
    jQuery.ajax({
        type: 'GET',
        url: wpf_cache_endpoint + 'stats/?blog_id=' + wpf_blog_id,
        async: true,
        complete: function (xhr, text) {
            var has_error = (xhr.statusText == 'error' || xhr.status != 200);
            wpf_indicator_off('#wpf_cache_stats', has_error, has_error ? 'Error, HTTP status ' + xhr.status : 'OK');
            if (!has_error) {
                var rows = xhr.responseText.trim().split("\n");
                rows.sort();
                var have_timestamps = false;
                jQuery.each(rows, function (i, row) {
                    row = row.split(' ');
                    if (row.length != 3)
                        return;
                    have_timestamps = true;
                    tbody.append('<tr><td>' + row[1] + '</td><td style="text-align: right; white-space: nowrap;">' + new Date(new Number(row[2]) * 1000) + '</td></tr>');
                });
                if (have_timestamps)
                    jQuery('#wpf_cache_stats_data').show();
                else
                    jQuery('#wpf_cache_stats_info').text("No timestamps in cache");
            }
        }
    });
}


function wpf_cache_ping() {
    wpf_indicator_on('#wpf_cache_ping');
    jQuery.ajax({
        type: 'POST',
        url: wpf_cache_endpoint + 'ping/',
        data: wpf_cache_ping_payload,
        async: true,
        complete: function (xhr, text) {
            wpf_indicator_off(
                '#wpf_cache_ping',
                (xhr.statusText == 'error' || xhr.responseText.indexOf('FAIL ') == 0),
                (typeof(xhr.responseText) !== 'undefined' && xhr.responseText ? xhr.responseText : xhr.statusText)
            );
        }
    });
}


function wpf_cache_command(command) {
    wpf_indicator_on('#wpf_cache_' + command);
    jQuery.ajax({
        type: 'POST',
        url: wpf_cache_endpoint + command + '/',
        data: wpf_cache_payloads[command],
        async: true,
        complete: function (xhr, text) {
            wpf_indicator_off(
                '#wpf_cache_' + command,
                (xhr.statusText == 'error' || xhr.responseText.indexOf('FAIL ') == 0),
                (typeof(xhr.responseText) !== 'undefined' && xhr.responseText ? xhr.responseText : xhr.statusText)
            );
        }
    });
}


jQuery(document).ready(function($) {
    $("#wpf_cache_regen").click(function() {
        wpf_cache_regen();
    });
    $('#wpf_cache_stats').click(function() {
        wpf_cache_stats();
    });
    $('#wpf_cache_ping').click(function() {
        wpf_cache_command('ping');
    });
    $('#wpf_cache_query').click(function() {
        wpf_cache_command('query');
    });
});
