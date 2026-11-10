// collect-spa-routing: CloudFront Function, runtime cloudfront-js-2.0,
// on the viewer-request event of the default cache behaviour.
// App pages like /bookings or /stores/0023 aren't files in S3,
// so send them the app itself. Real files pass through untouched.
function handler(event) {
    var request = event.request;
    var last = request.uri.split('/').pop();
    if (last.indexOf('.') === -1) {
        request.uri = '/index.html';
    }
    return request;
}
