function wpf_indicator_on(id) {
    jQuery(id + '_info').toggleClass('wpf_error', false);
    jQuery(id + '_info').text("Sending request");
    jQuery('html').css('cursor', 'wait');
    jQuery(id).css('cursor', 'wait');
}


function wpf_indicator_off(id, error, text) {
    jQuery('html').css('cursor', 'auto');
    jQuery(id).css('cursor', 'pointer');
    jQuery(id + '_info').toggleClass('wpf_error', error).text(text);
}


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
        url: wpf_cache_endpoint,
        data: 'do=cache',
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


function wpf_preformatter_batch_request(reset, iteration, num) {
    
    iteration++;
    
    var params = {action:'wpf_preformatter_batch', security:wpf_nonce};
    if (reset)
        params['reset'] = 1;
    
    jQuery.ajax({
        type: 'POST',
        url: ajaxurl,
        async: true,
        data: params,
        complete: function (xhr, text) {
            var error = null;
            if (xhr.statusText == 'error' || xhr.status != 200) {
                error = 'Request error, HTTP status ' + xhr.status;
            } else if (typeof(xhr.responseText) == 'undefined' || !xhr.responseText) {
                error = 'Response error, no data';
            }
            if (!error) {
                try { 
                    var data = jQuery.parseJSON(xhr.responseText);
                } catch(e) {
                    error = 'Error decoding response: ' + e;
                }
            }
            if (!error && data['error'])
                error = 'Server error: ' + data['error'];
            if (error) {
                wpf_indicator_off('#wpf_preformatter_batch_start', true, error);
                jQuery('#wpf_preformatter_batch_start').unbind('click').click(function() {wpf_preformatter_batch();});
                return;
            }
            
            num += data['num'];
            
            if (data['complete']) {
                wpf_indicator_off('#wpf_preformatter_batch_start', false, 'Batch preformatting completed with ' + iteration + ' requests, ' + num + ' total posts processed, last request time ' + data['time'] + ' seconds');
                jQuery('#wpf_preformatter_batch_start').unbind('click').click(function() {wpf_preformatter_batch();});
                return;
            }
            jQuery('#wpf_preformatter_batch_start_info').text('Batch iteration ' + iteration + ', start id ' + data['start'] + ', ' + num + ' total posts processed, last request time ' + data['time'] + ' seconds');
            wpf_preformatter_batch_request(false, iteration, num);
        }
    });
}

// wpf_preformatter_batch
function wpf_preformatter_batch() {
    jQuery('#wpf_preformatter_batch_start').unbind('click').click(function() { alert('Please wait for batch preformatting to complete'); });
    wpf_indicator_on('#wpf_preformatter_batch_start');
    wpf_preformatter_batch_request(true, 0, 0);
}


jQuery(document).ready(function($) {
    $("#wpf_cache_regen").click(function() {
        wpf_cache_regen();
    });
    $('#wpf_cache_stats').click(function() {
        wpf_cache_stats();
    });
    $('#wpf_cache_ping').click(function() {
        wpf_cache_ping();
    });
    $('#wpf_preformatter_batch_start').click(function() {
        wpf_preformatter_batch();
    });
    /*
    $('a.edit_taxonomy').click(function() {
        var $this = $(this);
        $('input#name').val($this.text());
        var row = $this.parents('tr');
        if (!row)
            return;
        row.children().each(function () {
            if (typeof(this.className) == 'undefined' || this.className.indexOf('taxonomy_') != 0)
                return;
            var attr_name = this.className.substring(9);
            if (attr_name == 'object_type') {
                var obj_types = this.innerText.split(', ');
                $('input.object_type').each(function () {
                    var $input = $(this);
                    if (obj_types.indexOf($input.val()) != -1)
                        $input.attr('checked', 'checked');
                    else
                        $input.removeAttr('checked');
                });
                return;
            }
            var $input = $('input#' + attr_name);
            switch ($input.attr('type')) {
                case 'text':
                    $input.val(this.innerText);
                    break;
                case 'checkbox':
                    if (this.innerText == 'Yes')
                        $input.attr('checked', 'checked');
                    else
                        $input.removeAttr('checked');
                    break;
            }
        });
        $('#submit-delete').show();
    });
    */
});
