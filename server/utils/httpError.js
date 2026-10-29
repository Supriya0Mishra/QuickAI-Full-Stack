// An error with an HTTP status code. Throw it from any route or middleware
// and the central error handler turns it into a JSON response.
export class HttpError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
