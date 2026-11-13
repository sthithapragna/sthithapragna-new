// collect-spa-routing: CloudFront Function, runtime cloudfront-js-2.0,
// on the viewer-request event of the default cache behaviour.
// Episode 07: www goes to the bare domain, so the site has one address.
// Episode 05: app pages like /bookings aren't files in S3, so serve the app.
function handler(event) {
    var req = event.request;
    var host = req.headers.host.value;
    if (host.indexOf('www.') === 0) {
        return { statusCode: 301, statusDescription: 'Moved Permanently',
            headers: { location: { value: 'https://' + host.slice(4) + req.uri } } };
    }
    var last = req.uri.split('/').pop();
    if (last.indexOf('.') === -1) {
        req.uri = '/index.html';
    }
    return req;
}
