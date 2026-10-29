import multer from "multer";

// Express 5 forwards errors from async handlers here automatically.
export const errorHandler = (err, req, res, next) => {
    if (err instanceof multer.MulterError) {
        const status = err.code === 'LIMIT_FILE_SIZE' ? 413 : 400;
        const message = err.code === 'LIMIT_FILE_SIZE' ? 'File is too large.' : err.message;
        return res.status(status).json({ success: false, message });
    }

    const status = err.status || 500;

    // Log unexpected errors, but don't send internal details to the client.
    if (status >= 500) {
        console.error(err);
        return res.status(status).json({ success: false, message: 'Something went wrong. Please try again.' });
    }

    res.status(status).json({ success: false, message: err.message });
};
