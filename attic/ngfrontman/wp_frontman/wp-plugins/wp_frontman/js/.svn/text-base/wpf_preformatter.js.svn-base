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
    $('#wpf_preformatter_batch_start').click(function() {
        wpf_preformatter_batch();
    });
});
