// Where Kestrel Collect gets its data.
//
// "sample": no cloud needed. Stores come from /sample/stores.json and slots
//           are generated in the browser. Used until the API exists.
// "live":   calls the Collect API. API_BASE is the API's address
//           (episode 15), or "" once the API is served from this site's
//           own domain under /api.
export const MODE = "sample";
export const API_BASE = "";
